#    Friendly Telegram (telegram userbot)
#    Copyright (C) 2018-2022 The Authors

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.

#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

#    Modded by GeekTG Team

import asyncio
import importlib
import inspect
import logging
import os
import re
import sys
import urllib
import uuid
from importlib.abc import SourceLoader
from importlib.machinery import ModuleSpec
import telethon
from telethon.tl.types import Message

import requests

from .. import loader, utils, main

logger = logging.getLogger(__name__)

VALID_URL = r"[-[\]_.~:/?#@!$&'()*+,;%<=>a-zA-Z0-9]+"
VALID_PIP_PACKAGES = re.compile(
    r"^\s*# requires:(?: ?)((?:{url} )*(?:{url}))\s*$".format(url=VALID_URL),
    re.MULTILINE,
)
USER_INSTALL = "PIP_TARGET" not in os.environ and "VIRTUAL_ENV" not in os.environ
GIT_REGEX = re.compile(
    r"^https?://github\.com((?:/[a-z0-9-]+){2})(?:/tree/([a-z0-9-]+)((?:/[a-z0-9-]+)*))?/?$",
    flags=re.IGNORECASE,
)


class StringLoader(
    SourceLoader
):  # pylint: disable=W0223 # False positive, implemented in SourceLoader
    """Load a python module/file from a string"""

    def __init__(self, data, origin):
        self.data = data.encode("utf-8") if isinstance(data, str) else data
        self.origin = origin

    def get_code(self, fullname):
        source = self.get_source(fullname)
        if source is None:
            return None
        return compile(source, self.origin, "exec", dont_inherit=True)

    def get_filename(self, fullname):
        return self.origin

    def get_data(self, filename):  # pylint: disable=W0221,W0613
        # W0613 is not fixable, we are overriding
        # W0221 is a false positive assuming docs are correct
        return self.data


def unescape_percent(text):
    i = 0
    ln = len(text)
    is_handling_percent = False
    out = ""

    while i < ln:
        char = text[i]

        if char == "%" and not is_handling_percent:
            is_handling_percent = True
            i += 1
            continue

        if char == "d" and is_handling_percent:
            out += "."
            is_handling_percent = False
            i += 1
            continue

        out += char
        is_handling_percent = False
        i += 1

    return out


def get_git_api(url):
    m = GIT_REGEX.search(url)

    if m is None:
        return None

    branch = m.group(2)
    path_ = m.group(3)
    api_url = f"https://api.github.com/repos{m.group(1)}/contents"

    if path_ is not None and len(path_) > 0:
        api_url += path_

    if branch:
        api_url += f"?ref={branch}"

    return api_url


@loader.tds
class LoaderMod(loader.Module):
    """Loads modules"""

    strings = {
        "name": "Linuxil_Loader",
        "repo_config_doc": "Полный URL-адрес репозитория модуля",
        "avail_header": "<b>☁️ Доступные официальные модули из репо</b>",
        "select_preset": "<b>⚠️ Выберите предустановку</b>",
        "no_preset": "<b>🚫 Предустановка не найдена</b>",
        "preset_loaded": "<b>✅ Предустановка загружена</b>",
        "no_module": "<b>🚫 Модуль недоступен в репозитории.</b>",
        "no_file": "<b>🚫 Файл не найден</b>",
        "provide_module": "<b>⚠️ Предоставьте модуль для загрузки</b>",
        "bad_unicode": "<b>🚫 Недопустимое форматирование Unicode в модуле</b>",
        "load_failed": "<b>🚫 Загрузка не удалась. Подробности смотрите в логах</b>",
        "loaded": "<b>🌟 Модуль </b><code>{}</code>{}<b> загружен.</b>{}",
        "no_class": "<b>Какой класс нужно выгрузить?</b>",
        "unloaded": "<b>🪄 Модуль выгружен.</b>",
        "not_unloaded": "<b>🚫 Модуль не выгружен.</b>",
        "requirements_failed": "<b>🚫 Установка требований не удалась</b>",
        "requirements_installing": "<b>🔄 Установка требований...</b>",
        "requirements_restart": "<b>🔄 Требования установлены, но требуется перезагрузка</b>",
        "all_modules_deleted": "<b>✅ Все модули удалены</b>",
        "no_modules": "<b>⚠️ У вас нет пользовательских модулей!</b>",
        "searching": "<b>🔍 Идет поиск...</b>",
        "file": "<b>📥 File of module {}:<b>",
        "module_link": '📥 <a href="{}">Link</a> for module {}: \n<code>{}</code>',
        "not_found_info": "🚫 Request to find module with name {} failed due to:",
        "not_found_c_info": "🚫 Request to find module with command {} failed due to:",
        "not_found": "<b>🚫 Модуль не найден</b>",
        "file_core": "<b>File of core module {}:</b>",
        "loading": "<b>🔄 Loading...</b>",
        "url_invalid": "<b>🚫 URL-адрес недействителен</b>",
        "args_incorrect": "<b>🚫 Неверные аргументы</b>",
        "repo_loaded": "<b>✅ Репозиторий загружен</b>",
        "repo_not_loaded": "<b>🚫 Репозиторий не загружен</b>",
        "repo_unloaded": "<b>🔄 Репозиторий выгружен, но для выгрузки модулей репозитория требуется перезагрузка</b>",
        "repo_not_unloaded": "<b>🚫 Репозиторий не выгружается</b>",
        "single_cmd": "\n🐾 <code>{}{}</code> 👉🏻 ",
        "undoc_cmd": "👁‍🗨 No docs",
        "ihandler": "\n🎹 <i>Inline</i>: <code>{}</code> 👉🏻 ",
        "undoc_ihandler": "👁‍🗨 No docs",
        "chandler": "\n🖱 <i>Callback</i>: <code>{}</code> 👉🏻 ",
        "undoc_chandler": "👁‍🗨 No docs",
        "inline_init_failed": (
            "🚫 <b>This module requires GeekTG inline feature and initialization of InlineManager failed</b>\n"
            "<i>Please, remove one of your old bots from @BotFather and restart userbot to load this module</i>"
        ),
        "version_incompatible": "🚫 <b>This module requires Linuxil {}+\nPlease, update with </b><code>.update</code>",
        "non_heroku": "♓️ <b>This module is not supported on Heroku</b>",
        "ffmpeg_required": "🚫 <b>This module requires FFMPEG, which is not installed</b>",
        "developer": "\n🧑‍💻 <b>Developer: </b><code>{}</code>",
    }

    def __init__(self):
        super().__init__()
        self.config = loader.ModuleConfig(
            "MODULES_REPO",
            "https://raw.githubusercontent.com/GeekTG/FTG-Modules/main/",
            lambda m: self.strings("repo_config_doc", m),
        )

    @loader.owner
    async def dlmodcmd(self, message: Message) -> None:
        """Downloads and installs a module from the official module repo"""
        if args := utils.get_args(message):
            args = args[0] if urllib.parse.urlparse(args[0]).netloc else args[0].lower()

            if await self.download_and_install(args, message):
                self._db.set(
                    __name__,
                    "loaded_modules",
                    list(
                        set(self._db.get(__name__, "loaded_modules", [])).union([args])
                    ),
                )
        else:
            text = utils.escape_html("\n".join(await self.get_repo_list("full")))
            await utils.answer(
                message,
                (
                    "<b>"
                    + self.strings("avail_header", message)
                    + "</b>\n"
                    + "\n".join(f"<code>{i}</code>" for i in sorted(text.split("\n")))
                ),
            )

    @loader.owner
    async def dlpresetcmd(self, message: Message) -> None:
        """Set preset. Defaults to full"""
        args = utils.get_args(message)

        if not args:
            await utils.answer(message, self.strings("select_preset", message))
            return

        try:
            await self.get_repo_list(args[0])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                await utils.answer(message, self.strings("no_preset", message))
                return

            raise

        self._db.set(__name__, "chosen_preset", args[0])
        self._db.set(__name__, "loaded_modules", [])
        self._db.set(__name__, "unloaded_modules", [])

        await utils.answer(message, self.strings("preset_loaded", message))
        await self.allmodules.commands["restart"](await message.reply("_"))

    async def _get_modules_to_load(self):
        todo = await self.get_repo_list(self._db.get(__name__, "chosen_preset", None))
        todo = todo.difference(self._db.get(__name__, "unloaded_modules", []))
        todo.update(self._db.get(__name__, "loaded_modules", []))
        return todo

    async def get_repo_list(self, preset=None):
        if preset is None or preset == "none":
            preset = "minimal"

        r = await utils.run_sync(
            requests.get, self.config["MODULES_REPO"] + "/" + preset + ".txt"
        )
        r.raise_for_status()
        return set(filter(lambda x: x, r.text.split("\n")))

    async def download_and_install(self, module_name, message=None):
        try:
            if urllib.parse.urlparse(module_name).netloc:
                url = module_name
            else:
                url = self.config["MODULES_REPO"] + module_name + ".py"

            r = await utils.run_sync(requests.get, url)

            if r.status_code == 404:
                if message is not None:
                    await utils.answer(message, self.strings("no_module", message))

                return False

            r.raise_for_status()
            return await self.load_module(
                r.content.decode("utf-8"), message, module_name, url
            )
        except Exception:
            logger.exception(f"Failed to load {module_name}")

    @loader.owner
    async def loadmodcmd(self, message: Message) -> None:
        """Loads the module file"""
        msg = message if message.file else (await message.get_reply_message())

        if msg is None or msg.media is None:
            if args := utils.get_args(message):
                try:
                    path_ = args[0]
                    with open(path_, "rb") as f:
                        doc = f.read()
                except FileNotFoundError:
                    await utils.answer(message, self.strings("no_file", message))
                    return
            else:
                await utils.answer(message, self.strings("provide_module", message))
                return
        else:
            path_ = None
            doc = await msg.download_media(bytes)

        logger.debug("Loading external module...")

        try:
            doc = doc.decode("utf-8")
        except UnicodeDecodeError:
            await utils.answer(message, self.strings("bad_unicode", message))
            return

        if path_ is not None:
            await self.load_module(doc, message, origin=path_)
        else:
            await self.load_module(doc, message)

    async def load_module(
        self, doc, message, name=None, origin="<string>", did_requirements=False
    ):
        if re.search(r"# ?scope: ?non_heroku", doc) and "DYNO" in os.environ:
            if isinstance(message, Message):
                await utils.answer(message, self.strings("non_heroku"))
            return

        if re.search(r"# ?scope: ?ffmpeg", doc) and os.system(
            "ffmpeg -version"
        ):  # skipcq: BAN-B605, BAN-B607
            if isinstance(message, Message):
                await utils.answer(message, self.strings("ffmpeg_required"))
            return

        if re.search(r"# ?scope: ?inline", doc) and not self.inline.init_complete:
            if isinstance(message, Message):
                await utils.answer(message, self.strings("inline_init_failed"))
            return

        if re.search(r"# ?scope: ?geektg_min", doc):
            ver = re.search(
                r"# ?scope: ?geektg_min ([0-9]+\.[0-9]+\.[0-9]+)", doc
            ).group(1)
            ver_ = tuple(map(int, ver.split(".")))
            if main.__version__ < ver_:
                await utils.answer(
                    message, self.strings("version_incompatible").format(ver)
                )
                return

        developer = re.search(r"# ?meta developer: ?(.+)", doc)
        developer = developer.group(1) if developer else False
        developer = self.strings("developer").format(developer) if developer else ""

        if name is None:
            uid = "__extmod_" + str(uuid.uuid4())
        else:
            uid = name.replace("%", "%%").replace(".", "%d")

        module_name = "friendly-telegram.modules." + uid

        try:
            try:
                spec = ModuleSpec(module_name, StringLoader(doc, origin), origin=origin)
                instance = self.allmodules.register_module(spec, module_name, origin)
            except ImportError:
                logger.info(
                    "Module loading failed, attemping dependency installation",
                    exc_info=True,
                )
                # Let's try to reinstall dependencies
                requirements = list(
                    filter(
                        lambda x: x and x[0] not in ("-", "_", "."),
                        map(str.strip, VALID_PIP_PACKAGES.search(doc)[1].split(" ")),
                    )
                )

                logger.debug("Installing requirements: %r", requirements)

                if not requirements:
                    raise  # we don't know what to install

                if did_requirements:
                    if message is not None:
                        await utils.answer(
                            message, self.strings("requirements_restart", message)
                        )

                    return True  # save to database despite failure

                if message is not None:
                    await utils.answer(
                        message, self.strings("requirements_installing", message)
                    )

                pip = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "-q",
                    "--disable-pip-version-check",
                    "--no-warn-script-location",
                    *["--user"] if USER_INSTALL else [],
                    *requirements,
                )

                rc = await pip.wait()

                if rc != 0:
                    if message is not None:
                        await utils.answer(
                            message, self.strings("requirements_failed", message)
                        )

                    return False

                importlib.invalidate_caches()

                return await self.load_module(
                    doc, message, name, origin, True
                )  # Try again
            except loader.LoadError as e:
                if message:
                    await utils.answer(message, f"🚫 <b>{utils.escape_html(str(e))}</b>")
                return
        except BaseException as e:
            logger.exception(f"Loading external module failed due to {e}")

            if message is not None:
                await utils.answer(message, self.strings("load_failed", message))

            return False

        instance.inline = self.inline
        if hasattr(instance, "__version__") and isinstance(instance.__version__, tuple):
            version = (
                "<b><i> (v"
                + ".".join(list(map(str, list(instance.__version__))))
                + ")</i></b>"
            )
        else:
            version = ""

        try:
            try:
                self.allmodules.send_config_one(instance, self._db, self.babel)
                await self.allmodules.send_ready_one(
                    instance, self._client, self._db, self.allclients
                )
            except loader.LoadError as e:
                if message:
                    await utils.answer(message, f"🚫 <b>{utils.escape_html(str(e))}</b>")
                return
        except Exception as e:
            logger.exception(f"Module threw because {e}")

            if message is not None:
                await utils.answer(message, self.strings("load_failed", message))

            return False

        if message is not None:
            try:
                modname = instance.strings("name", message)
            except KeyError:
                modname = getattr(instance, "name", "ERROR")

            modhelp = ""
            prefix = utils.escape_html(
                (self._db.get(main.__name__, "command_prefix", False) or ".")
            )

            if instance.__doc__:
                modhelp += (
                    f"<i>\nℹ️ {utils.escape_html(inspect.getdoc(instance))}</i>\n"
                )

            if re.search(r"# ?scope: ?disable_onload_docs", doc):
                return await utils.answer(
                    message,
                    self.strings("loaded", message).format(
                        modname.strip(), version, modhelp
                    )
                    + developer,
                )

            for _name, fun in instance.commands.items():
                modhelp += self.strings("single_cmd", message).format(prefix, _name)

                if fun.__doc__:
                    modhelp += utils.escape_html(inspect.getdoc(fun))
                else:
                    modhelp += self.strings("undoc_cmd", message)

            if self.inline.init_complete:
                if hasattr(instance, "inline_handlers"):
                    for _name, fun in instance.inline_handlers.items():
                        modhelp += self.strings("ihandler", message).format(
                            f"@{self.inline._bot_username} {_name}"
                        )

                        if fun.__doc__:
                            modhelp += utils.escape_html(
                                "\n".join(
                                    [
                                        line.strip()
                                        for line in inspect.getdoc(fun).splitlines()
                                        if not line.strip().startswith("@")
                                    ]
                                )
                            )
                        else:
                            modhelp += self.strings("undoc_ihandler", message)

                if hasattr(instance, "callback_handlers"):
                    for _name, fun in instance.callback_handlers.items():
                        modhelp += self.strings("chandler", message).format(_name)

                        if fun.__doc__:
                            modhelp += utils.escape_html(
                                "\n".join(
                                    [
                                        line.strip()
                                        for line in inspect.getdoc(fun).splitlines()
                                        if not line.strip().startswith("@")
                                    ]
                                )
                            )
                        else:
                            modhelp += self.strings("undoc_chandler", message)

            try:
                await utils.answer(
                    message,
                    self.strings("loaded", message).format(
                        modname.strip(), version, modhelp
                    )
                    + developer,
                )
            except telethon.errors.rpcerrorlist.MediaCaptionTooLongError:
                await message.reply(
                    self.strings("loaded", message).format(
                        modname.strip(), version, modhelp
                    )
                    + developer
                )

        return True

    @loader.owner
    async def dlrepocmd(self, message: Message) -> None:
        """Downloads and installs all modules from repo"""
        args = utils.get_args(message)

        if len(args) == 1:
            repo_url = args[0]
            git_api = get_git_api(repo_url)

            if git_api is None:
                return await utils.answer(message, self.strings("url_invalid", message))

            await utils.answer(message, self.strings("loading", message))

            if await self.load_repo(git_api):
                self._db.set(
                    __name__,
                    "loaded_repositories",
                    list(
                        set(self._db.get(__name__, "loaded_repositories", [])).union(
                            [repo_url]
                        )
                    ),
                )

                await utils.answer(message, self.strings("repo_loaded", message))
            else:
                await utils.answer(message, self.strings("repo_not_loaded", message))
        else:
            await utils.answer(message, self.strings("args_incorrect", message))

    @loader.owner
    async def unloadrepocmd(self, message: Message) -> None:
        """Removes loaded repository"""
        args = utils.get_args(message)

        if len(args) == 1:
            repoUrl = args[0]
            repos = set(self._db.get(__name__, "loaded_repositories", []))

            try:
                repos.remove(repoUrl)
            except KeyError:
                return await utils.answer(
                    message, self.strings("repo_not_unloaded", message)
                )

            self._db.set(__name__, "loaded_repositories", list(repos))

            await utils.answer(message, self.strings("repo_unloaded", message))
        else:
            await utils.answer(message, self.strings("args_incorrect", message))

    async def load_repo(self, git_api):
        req = await utils.run_sync(requests.get, git_api)

        if req.status_code != 200:
            return False

        files = req.json()

        if not isinstance(files, list):
            return False

        await asyncio.gather(
            *[
                self.download_and_install(f["download_url"])
                for f in filter(
                    lambda f: f["name"].endswith(".py") and f["type"] == "file", files
                )
            ]
        )
        return True

    @loader.owner
    async def unloadmodcmd(self, message: Message) -> None:
        """Unload module by class name"""
        args = utils.get_args_raw(message)

        if not args:
            await utils.answer(message, self.strings("no_class", message))
            return

        worked = self.allmodules.unload_module(
            args.capitalize()
        ) + self.allmodules.unload_module(args)
        without_prefix = []

        for mod in worked:
            if not mod.startswith("friendly-telegram.modules.") or not mod:
                raise Exception("Assertion error")

            without_prefix += [
                unescape_percent(mod[len("friendly-telegram.modules.") :])
            ]

        it = set(self._db.get(__name__, "loaded_modules", [])).difference(
            without_prefix
        )
        self._db.set(__name__, "loaded_modules", list(it))
        it = set(self._db.get(__name__, "unloaded_modules", [])).union(without_prefix)
        self._db.set(__name__, "unloaded_modules", list(it))

        await utils.answer(
            message, self.strings("unloaded" if worked else "not_unloaded", message)
        )

    @loader.owner
    async def clearmodulescmd(self, message: Message) -> None:
        """Delete all installed modules"""
        self._db.set("friendly-telegram.modules.loader", "loaded_modules", [])
        self._db.set("friendly-telegram.modules.loader", "unloaded_modules", [])

        await utils.answer(message, self.strings("all_modules_deleted", message))

        self._db.set(__name__, "chosen_preset", "none")

        await self.allmodules.commands["restart"](await message.reply("_"))

    async def _update_modules(self):
        todo = await self._get_modules_to_load()

        await asyncio.gather(*[self.download_and_install(mod) for mod in todo])

        repos = set(self._db.get(__name__, "loaded_repositories", []))

        await asyncio.gather(*[self.load_repo(get_git_api(url)) for url in repos])

    async def client_ready(self, client, db):
        self._db = db
        self._client = client
        await self._update_modules()


def get_module(module):
    name = module.name
    sysmod = sys.modules.get(module.__module__)
    origin = sysmod.__spec__.origin
    loader_ = sysmod.__loader__
    cname = type(loader_).__name__
    r = [name, None, None]

    if cname == "SourceFileLoader":
        r[1] = "path"
        r[2] = loader_.get_filename()
    elif cname == "StringLoader":
        if origin == "<string>":
            r[1] = "text"
            r[2] = loader_.data
        else:
            r[1] = "link"
            r[2] = origin

    return r
