"""MONAI VILA-M3 session — loads Llama3-VILA-M3 and runs the expert agent loop."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_CARDS = (
    "Here is a list of available expert models:\n"
    "<VISTA3D(args)> Modality: CT, Task: segmentation, Valid args: 'organs', 'lung tumor', "
    "'hepatic tumor', 'everything'\n"
    "<CXR(args)> Modality: chest x-ray, Task: classification, Valid args are: None\n"
    "Give the model <NAME(args)> when selecting a suitable expert model.\n"
)

_ANALYZE_PROMPT = (
    "Analyze this medical image for abnormalities. Describe findings with anatomical location, "
    "likely severity, and clinical recommendations. Trigger an appropriate expert model "
    "(VISTA3D for CT segmentation, CXR for chest x-ray classification) when it would improve "
    "your answer."
)


class VilaM3Session:
    """Wraps MONAI M3Generator + expert models from VLM-Radiology-Agent-Framework."""

    def __init__(
        self,
        model_path: str,
        *,
        source: str = "local",
        conv_mode: str = "llama_3",
    ) -> None:
        self.model_path = model_path
        self.source = source
        self.conv_mode = conv_mode
        self._generator = None
        self._experts = None
        self._sys_prompt: str | None = None
        self._load()

    def _monai_demo_dir(self) -> Path:
        root = Path(os.getenv("VILA_M3_MONAI_ROOT", "/opt/VLM-Radiology-Agent-Framework"))
        demo = root / "m3" / "demo"
        if not demo.is_dir():
            raise FileNotFoundError(f"MONAI m3/demo not found at {demo}")
        return demo

    def _setup_import_paths(self) -> None:
        demo = self._monai_demo_dir()
        vila = demo.parent.parent / "thirdparty" / "VILA"
        for p in (str(demo), str(vila)):
            if p not in sys.path:
                sys.path.insert(0, p)

    @staticmethod
    def _install_deepspeed_stub() -> None:
        """VILA pulls deepspeed via train imports; inference-only does not need it."""
        if "deepspeed" in sys.modules:
            return
        import importlib.util

        comm_spec = importlib.util.spec_from_loader("deepspeed.comm", loader=None)
        comm = importlib.util.module_from_spec(comm_spec)
        comm.get_rank = lambda group=None: 0  # noqa: ARG005
        comm.get_world_size = lambda group=None: 1  # noqa: ARG005
        comm.new_group = lambda ranks: object()
        comm.init_distributed = lambda *args, **kwargs: None
        comm.is_initialized = lambda: False

        ds_spec = importlib.util.spec_from_loader("deepspeed", loader=None)
        deepspeed = importlib.util.module_from_spec(ds_spec)
        deepspeed.comm = comm
        sys.modules["deepspeed"] = deepspeed
        sys.modules["deepspeed.comm"] = comm

    def _load(self) -> None:
        self._setup_import_paths()
        self._install_deepspeed_stub()
        import torch
        from huggingface_hub import snapshot_download
        from llava.conversation import conv_templates
        from llava.mm_utils import get_model_name_from_path
        from llava.model.builder import load_pretrained_model
        from llava.utils import disable_torch_init

        from experts.expert_monai_brats import ExpertBrats
        from experts.expert_monai_vista3d import ExpertVista3D
        from experts.expert_torchxrayvision import ExpertTXRV

        disable_torch_init()
        path = self.model_path
        if self.source == "huggingface":
            path = snapshot_download(path)
        elif not os.path.isdir(path):
            raise FileNotFoundError(f"VILA checkpoint not found: {path}")

        model_name = get_model_name_from_path(path)
        tokenizer, model, image_processor, context_len = load_pretrained_model(path, model_name)
        logger.info("VILA-M3 loaded: %s (ctx=%s)", model_name, context_len)

        self._tokenizer = tokenizer
        self._model = model
        self._image_processor = image_processor
        self._context_len = context_len
        self._sys_prompt = conv_templates[self.conv_mode].system
        self._experts = (ExpertTXRV, ExpertVista3D, ExpertBrats)
        self._conv_mode = self.conv_mode
        self._device = model.device

    def _generate_local(
        self,
        messages: list,
        *,
        max_tokens: int = 768,
        temperature: float = 0.0,
        top_p: float = 0.9,
        system_prompt: str | None = None,
    ) -> str:
        import torch
        from llava.constants import IMAGE_TOKEN_INDEX
        from llava.conversation import SeparatorStyle, conv_templates
        from llava.mm_utils import KeywordsStoppingCriteria, process_images, tokenizer_image_token
        from experts.utils import load_image

        images = []
        conv = conv_templates[self._conv_mode].copy()
        if system_prompt:
            conv.system = system_prompt
        user_role, assistant_role = conv.roles[0], conv.roles[1]

        for message in messages:
            role = user_role if message["role"] == "user" else assistant_role
            prompt = ""
            for content in message["content"]:
                if content["type"] == "text":
                    prompt += content["text"]
                if content["type"] == "image_path":
                    paths = (
                        content["image_path"]
                        if isinstance(content["image_path"], list)
                        else [content["image_path"]]
                    )
                    for p in paths:
                        images.append(load_image(p))
            conv.append_message(role, prompt)

        if conv.sep_style == SeparatorStyle.LLAMA_3:
            conv.append_message(assistant_role, "")

        prompt_text = conv.get_prompt()
        images_tensor = None
        if images:
            images_tensor = process_images(images, self._image_processor, self._model.config).to(
                self._model.device, dtype=torch.float16
            )
        input_ids = (
            tokenizer_image_token(
                prompt_text, self._tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt"
            )
            .unsqueeze(0)
            .to(self._model.device)
        )
        stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
        stopping = KeywordsStoppingCriteria([stop_str], self._tokenizer, input_ids)

        with torch.inference_mode():
            output_ids = self._model.generate(
                input_ids,
                images=[images_tensor] if images_tensor is not None else None,
                do_sample=temperature > 0,
                temperature=temperature,
                top_p=top_p,
                num_beams=1,
                max_new_tokens=max_tokens,
                use_cache=True,
                stopping_criteria=[stopping],
                pad_token_id=self._tokenizer.eos_token_id,
                min_new_tokens=2,
            )
        outputs = self._tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0].strip()
        if outputs.endswith(stop_str):
            outputs = outputs[: -len(stop_str)].strip()
        return outputs

    @staticmethod
    def _squash_expert_messages(messages: list) -> list:
        messages = deepcopy(messages)
        i = 0
        while i < len(messages):
            if messages[i]["role"] == "expert":
                messages[i]["role"] = "user"
                j = i + 1
                while j < len(messages) and messages[j]["role"] == "expert":
                    messages[i]["content"].extend(messages[j]["content"])
                    j += 1
                del messages[i + 1 : j]
            i += 1
        return messages

    def run_agent(
        self,
        image_path: str,
        prompt: str,
        *,
        modality: str = "CT",
        use_model_cards: bool = True,
    ) -> tuple[str, list[str], list[str]]:
        """Run VILA-M3 with optional expert follow-up.

        Returns (final_answer, expert_notes, expert_overlay_image_paths).
        """
        mod_msg = f"This is a {modality} image.\n" if modality else ""
        cards = MODEL_CARDS if use_model_cards else ""
        user_text = f"{cards}{mod_msg}{prompt}"

        messages: list[dict] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_path", "image_path": image_path},
                ],
            }
        ]
        expert_notes: list[str] = []
        expert_images: list[str] = []
        work_dir = tempfile.mkdtemp(prefix="vila-expert-")

        outputs = self._generate_local(
            self._squash_expert_messages(messages),
            system_prompt=self._sys_prompt,
        )
        messages.append(
            {"role": "assistant", "content": [{"type": "text", "text": outputs}]}
        )

        expert = None
        for expert_cls in self._experts:
            inst = expert_cls()
            if inst.mentioned_by(outputs):
                expert = inst
                break

        if expert:
            logger.info("Triggering expert %s", expert.__class__.__name__)
            try:
                text_out, seg_image, instruction = expert.run(
                    image_url=image_path,
                    input=outputs,
                    output_dir=work_dir,
                    img_file=image_path,
                    slice_index=None,
                    prompt=prompt,
                )
                if text_out:
                    expert_notes.append(text_out)
                    messages.append(
                        {
                            "role": "expert",
                            "content": [{"type": "text", "text": text_out}],
                        }
                    )
                if seg_image:
                    expert_images.append(seg_image)
                    messages.append(
                        {
                            "role": "expert",
                            "content": [
                                {"type": "text", "text": "Segmentation overlay:"},
                                {"type": "image_path", "image_path": seg_image},
                            ],
                        }
                    )
                if instruction:
                    expert_notes.append(instruction)
                    messages.append(
                        {
                            "role": "expert",
                            "content": [{"type": "text", "text": instruction}],
                        }
                    )
                outputs = self._generate_local(
                    self._squash_expert_messages(messages),
                    system_prompt=self._sys_prompt,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Expert model failed")
                expert_notes.append(f"Expert error: {exc}")

        return outputs, expert_notes, expert_images

    def analyze_study_prompt(self) -> str:
        return _ANALYZE_PROMPT

    def qa_prompt(
        self,
        question: str,
        *,
        modality: str | None = None,
        body_part: str | None = None,
        description: str | None = None,
        findings_summary: list[dict] | None = None,
    ) -> str:
        """Build an image-grounded VQA prompt for the AI chat panel."""
        parts = [
            "Answer the radiologist's question using the provided medical image.",
            "Inspect visible anatomy and any abnormalities directly from the image.",
            "When describing tumors, nodules, or lesions, include structured details:",
            "label, anatomical location, size (cm or mm), and confidence (0-100%).",
            "If expert segmentation (VISTA3D) or chest X-ray classification (CXR) would "
            "improve your answer, trigger the appropriate expert model.",
        ]
        if modality:
            parts.append(f"Modality: {modality}.")
        if body_part:
            parts.append(f"Body part: {body_part}.")
        if description:
            parts.append(description.strip())
        if findings_summary:
            parts.append("Prior AI findings (verify against the image):")
            for f in findings_summary:
                size = ""
                if f.get("size_cm"):
                    size = f", size {f['size_cm']} cm"
                elif f.get("volume_cc"):
                    size = f", volume {f['volume_cc']} cc"
                parts.append(
                    f"- {f.get('label', '?')} at {f.get('location', '?')}"
                    f"{size} ({int(float(f.get('confidence', 0)) * 100)}% confidence)"
                )
        parts.append(f"\nQuestion: {question.strip()}")
        return "\n".join(parts)
