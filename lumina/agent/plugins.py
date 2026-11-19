from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

import yaml

logger = logging.getLogger("lumina")


class PluginManager:
    """加载 plugins/ 目录下的插件：每个插件一个子目录，含 manifest.yaml + main.py。

    main.py 里定义一个 Plugin 类，含 register(registry, context)（可注册工具），
    可选 async start() / async stop()。
    """

    def __init__(self, plugin_dir: str):
        self.dir = Path(plugin_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.plugins: dict[str, dict] = {}

    def load(self, registry) -> list[dict]:
        for sub in sorted(self.dir.iterdir()):
            if not sub.is_dir():
                continue
            manifest_file = sub / "manifest.yaml"
            main_file = sub / "main.py"
            if not main_file.exists():
                continue
            try:
                manifest = {}
                if manifest_file.exists():
                    manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
                name = manifest.get("name") or sub.name

                spec = importlib.util.spec_from_file_location(
                    f"lumina_plugin_{name}", main_file
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                cls = getattr(mod, "Plugin", None)
                if cls is None:
                    logger.warning("plugin %s 无 Plugin 类", name)
                    continue
                instance = cls()
                instance.register(registry, {})
                self.plugins[name] = {
                    "manifest": manifest, "instance": instance, "dir": sub,
                    "running": False,
                }
                logger.info("plugin %s loaded", name)
            except Exception as e:  # noqa: BLE001
                logger.warning("plugin %s load failed: %s", sub.name, e)
        return self.list_plugins()

    def list_plugins(self) -> list[dict]:
        return [
            {
                "name": name,
                "version": p["manifest"].get("version", ""),
                "description": p["manifest"].get("description", ""),
                "running": p.get("running", False),
            }
            for name, p in self.plugins.items()
        ]

    async def start(self, name: str) -> dict:
        p = self.plugins.get(name)
        if not p:
            return {"error": f"插件 {name} 不存在"}
        start = getattr(p["instance"], "start", None)
        if start:
            await start()
        p["running"] = True
        return {"started": True, "name": name}

    async def stop(self, name: str) -> dict:
        p = self.plugins.get(name)
        if not p:
            return {"error": f"插件 {name} 不存在"}
        stop = getattr(p["instance"], "stop", None)
        if stop:
            await stop()
        p["running"] = False
        return {"stopped": True, "name": name}
