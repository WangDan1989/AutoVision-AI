import asyncio
import random
from pathlib import Path

import httpx

from app.core.config import settings


class ComfyUIService:
    def _build_z_image_turbo_workflow(
        self,
        positive_prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        filename_prefix: str,
        seed: int | None = None,
    ) -> dict:
        actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)
        try:
            w = int(width)
            h = int(height)
        except (TypeError, ValueError):
            w, h = 1024, 1024
        w = w - (w % 16)
        h = h - (h % 16)

        workflow: dict = {
            "66": {
                "inputs": {
                    "unet_name": settings.COMFYUI_Z_UNET,
                    "weight_dtype": "default",
                },
                "class_type": "UNETLoader",
            },
            "62": {
                "inputs": {
                    "clip_name": settings.COMFYUI_Z_CLIP,
                    "type": "lumina2",
                    "device": "default",
                },
                "class_type": "CLIPLoader",
            },
            "63": {
                "inputs": {
                    "vae_name": settings.COMFYUI_Z_VAE,
                },
                "class_type": "VAELoader",
            },
            "68": {
                "inputs": {
                    "width": w,
                    "height": h,
                    "batch_size": 1,
                },
                "class_type": "EmptySD3LatentImage",
            },
            "69": {
                "inputs": {
                    "model": ["66", 0],
                    "shift": settings.COMFYUI_Z_SIGMA,
                },
                "class_type": "ModelSamplingAuraFlow",
            },
            "67": {
                "inputs": {
                    "text": positive_prompt,
                    "clip": ["62", 0],
                },
                "class_type": "CLIPTextEncode",
            },
            "71": {
                "inputs": {
                    "text": negative_prompt,
                    "clip": ["62", 0],
                },
                "class_type": "CLIPTextEncode",
            },
            "70": {
                "inputs": {
                    "seed": actual_seed,
                    "control_after_generate": "fixed",
                    "steps": settings.COMFYUI_Z_STEPS,
                    "cfg": settings.COMFYUI_Z_CFG,
                    "sampler_name": settings.COMFYUI_Z_SAMPLER,
                    "scheduler": settings.COMFYUI_Z_SCHEDULER,
                    "denoise": 1,
                    "model": ["69", 0],
                    "positive": ["67", 0],
                    "negative": ["71", 0],
                    "latent_image": ["68", 0],
                },
                "class_type": "KSampler",
            },
            "65": {
                "inputs": {
                    "samples": ["70", 0],
                    "vae": ["63", 0],
                },
                "class_type": "VAEDecode",
            },
            "9": {
                "inputs": {
                    "filename_prefix": filename_prefix or "ComfyUI",
                    "images": ["65", 0],
                },
                "class_type": "SaveImage",
            },
        }
        return workflow

    def _build_sd15_workflow(
        self,
        positive_prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        filename_prefix: str,
        lora_name: str = "",
        lora_weight: float = 0.75,
        seed: int | None = None,
    ) -> dict:
        if not settings.COMFYUI_CHECKPOINT:
            raise ValueError("未配置 COMFYUI_CHECKPOINT，无法调用 SD1.5 管线")

        base_loader_id = "4"
        positive_clip_ref = ["4", 1]
        sampler_model_ref = ["4", 0]
        actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)

        workflow: dict = {
            "4": {
                "inputs": {"ckpt_name": settings.COMFYUI_CHECKPOINT},
                "class_type": "CheckpointLoaderSimple",
            }
        }

        if lora_name:
            workflow["10"] = {
                "inputs": {
                    "model": ["4", 0],
                    "clip": ["4", 1],
                    "lora_name": lora_name,
                    "strength_model": lora_weight,
                    "strength_clip": lora_weight,
                },
                "class_type": "LoraLoader",
            }
            sampler_model_ref = ["10", 0]
            positive_clip_ref = ["10", 1]

        workflow.update(
            {
                "5": {
                    "inputs": {"width": width, "height": height, "batch_size": 1},
                    "class_type": "EmptyLatentImage",
                },
                "6": {
                    "inputs": {"text": positive_prompt, "clip": positive_clip_ref},
                    "class_type": "CLIPTextEncode",
                },
                "7": {
                    "inputs": {"text": negative_prompt, "clip": positive_clip_ref},
                    "class_type": "CLIPTextEncode",
                },
                "3": {
                    "inputs": {
                        "seed": actual_seed,
                        "steps": 24,
                        "cfg": 7,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "denoise": 1,
                        "model": sampler_model_ref,
                        "positive": ["6", 0],
                        "negative": ["7", 0],
                        "latent_image": ["5", 0],
                    },
                    "class_type": "KSampler",
                },
                "8": {
                    "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                    "class_type": "VAEDecode",
                },
                "9": {
                    "inputs": {"filename_prefix": filename_prefix, "images": ["8", 0]},
                    "class_type": "SaveImage",
                },
            }
        )
        return workflow

    def _select_pipeline(self) -> str:
        pipeline = (settings.COMFYUI_PIPELINE or "").strip().upper()
        if pipeline == "Z_IMAGE_TURBO":
            return "Z_IMAGE_TURBO"
        if pipeline == "SD15":
            return "SD15"
        if settings.COMFYUI_Z_UNET and settings.COMFYUI_Z_CLIP and settings.COMFYUI_Z_VAE:
            return "Z_IMAGE_TURBO"
        if settings.COMFYUI_CHECKPOINT:
            return "SD15"
        raise ValueError("未配置可用的 ComfyUI 管线 (Z_IMAGE_TURBO 或 SD15)")

    async def generate_image(
        self,
        positive_prompt: str,
        width: int,
        height: int,
        filename_prefix: str,
        lora_name: str = "",
        lora_weight: float = 0.75,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> dict:
        if negative_prompt is None:
            negative_prompt = settings.COMFYUI_NEGATIVE_PROMPT or ""

        pipeline = self._select_pipeline()
        try:
            w_int = int(width)
            h_int = int(height)
        except (TypeError, ValueError):
            w_int, h_int = 1024, 1024
        w_align = w_int - (w_int % 16)
        h_align = h_int - (h_int % 16)
        if pipeline == "Z_IMAGE_TURBO":
            workflow = self._build_z_image_turbo_workflow(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                width=w_align,
                height=h_align,
                filename_prefix=filename_prefix,
                seed=seed,
            )
        else:
            workflow = self._build_sd15_workflow(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                width=w_align,
                height=h_align,
                filename_prefix=filename_prefix,
                lora_name=lora_name,
                lora_weight=lora_weight,
                seed=seed,
            )

        try:
            async with httpx.AsyncClient(timeout=1800) as client:
                resp = await client.post(
                    f"{settings.COMFYUI_BASE_URL.rstrip('/')}/prompt",
                    json={"prompt": workflow},
                )
                resp.raise_for_status()
                payload = resp.json()
                prompt_id = payload.get("prompt_id")
                if not prompt_id:
                    raise ValueError("ComfyUI 未返回 prompt_id")

                history = None
                for _ in range(1800):
                    history_resp = await client.get(
                        f"{settings.COMFYUI_BASE_URL.rstrip('/')}/history/{prompt_id}"
                    )
                    history_resp.raise_for_status()
                    history_payload = history_resp.json()
                    if prompt_id in history_payload:
                        history = history_payload[prompt_id]
                        break
                    await asyncio.sleep(1)

                if not history:
                    raise TimeoutError("等待 ComfyUI 出图超时")

                image_info = None
                for output in history.get("outputs", {}).values():
                    if output.get("images"):
                        image_info = output["images"][0]
                        break

                if not image_info:
                    raise ValueError("ComfyUI 未返回图片输出")

                image_bytes = await client.get(
                    f"{settings.COMFYUI_BASE_URL.rstrip('/')}/view",
                    params={
                        "filename": image_info["filename"],
                        "subfolder": image_info.get("subfolder", ""),
                        "type": image_info.get("type", "output"),
                    },
                )
                image_bytes.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"无法连接 ComfyUI 服务，请确认已启动并检查 COMFYUI_BASE_URL={settings.COMFYUI_BASE_URL}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("等待 ComfyUI 响应超时，请检查模型加载状态或工作流执行耗时") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"ComfyUI 接口返回异常 HTTP {exc.response.status_code}，请检查工作流节点与模型配置"
            ) from exc

        output_dir = settings.media_root_path / settings.IMAGES_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{filename_prefix}.png"
        Path(output_path).write_bytes(image_bytes.content)

        return {
            "image_path": str(output_path),
            "width": w_align,
            "height": h_align,
            "prompt_id": prompt_id,
            "pipeline": pipeline,
        }
