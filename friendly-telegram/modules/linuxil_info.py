"""
    █ █ ▀ █▄▀ ▄▀█ █▀█ ▀    ▄▀█ ▀█▀ ▄▀█ █▀▄▀█ ▄▀█
    █▀█ █ █ █ █▀█ █▀▄ █ ▄  █▀█  █  █▀█ █ ▀ █ █▀█

    Copyright 2022 t.me/hikariatama
    Licensed under the GNU GPLv3
"""

# scope: inline

from .. import loader, main, utils
import logging
import aiogram
import git
from aiogram.types.input_message_content import InputTextMessageContent

from telethon.utils import get_display_name
from ..inline import GeekInlineQuery, rand

logger = logging.getLogger(__name__)


@loader.tds
class GeekInfoMod(loader.Module):
    """Show userbot info (geek3.1.0alpha+)"""

    strings = {
        "name": "Linuxil_Info",
        "_custom_msg_doc": "Вы можете использовать эти ключевые слова  {owner}, {version}, {build}, {upd}, {platform} ",
        "_custom_button_doc": "Пользовательские кнопки.",
        "_photo_url_doc": "You can set your own photo to geek info.",
        "default_message": (
            "<b>🤴 Владелец:</b> {owner}\n"
            "<b>⚡ Версия:</b> <i>{version} #{build}</i>\n"
            "<b>{upd}</b>\n\n"
            "<b>📼 Хост: {platform}</b>\n"
        ),
    }

    def get(self, *args) -> dict:
        return self._db.get(self.strings["name"], *args)

    def set(self, *args) -> None:
        return self._db.set(self.strings["name"], *args)

    async def client_ready(self, client, db) -> None:
        self._db = db
        self._client = client
        self._me = await client.get_me()

    def __init__(self):
        self.config = loader.ModuleConfig(
            "custom_message",
            False,
            lambda: self.strings("_custom_msg_doc"),
            "custom_buttons",
            {"text": "👾 Support chat", "url": "https://t.me/Linuxil_talks"},
            lambda: self.strings("_custom_button_doc"),
            "photo_url",
            "https://i.imgur.com/0Z1ZTpm.jpeg",
            lambda: self.strings("_photo_url_doc"),
        )

    def build_message(self):
        """
        Build custom message
        """
        try:
            repo = git.Repo()
            diff = repo.git.log(["HEAD..origin", "--oneline"])
            upd = (
                "⚠️ Требуется обнова </b><code>.update</code><b>"
                if diff
                else "📯 Актуальная версия"
            )
        except Exception:
            upd = ""
        ver, gitlink = utils.get_git_info()
        try:
            return (
                self.config["custom_message"]
                if self.config["custom_message"]
                else self.strings("default_message")
            ).format(
                owner=f'<a href="tg://user?id={self._me.id}">{get_display_name(self._me)}</a>',
                version=utils.get_version_raw(),
                build=f'<a href="{gitlink}">{ver[:8] or "Unknown"}</a>',
                upd=upd,
                platform=utils.get_platform_name(),
            )
        except KeyError:
            return self.strings("default_message").format(
                owner=f'<a href="tg://user?id={self._me.id}">{get_display_name(self._me)}</a>',
                version=utils.get_version_raw(),
                build=f'<a href="{gitlink}">{ver[:8] or "Unknown"}</a>',
                upd=upd,
                platform=utils.get_platform_name(),
            )

    async def info_inline_handler(self, query: GeekInlineQuery) -> None:
        """
        Send userbot info
        @allow: all
        """

        await query.answer(
            [
                aiogram.types.inline_query_result.InlineQueryResultPhoto(
                    id=rand(20),
                    photo_url=self.config["photo_url"],
                    title="Send userbot info",
                    description="ℹ This will not compromise any sensitive data",
                    caption=self.build_message(),
                    parse_mode="html",
                    thumb_url="https://siasky.net/fAGDN9wfyejR3vtdnjzZVguNQABe7fDB0gguBjF0DF3WjQ",  # noqa: E501
                    reply_markup=self.inline._generate_markup(
                        self.config["custom_buttons"]
                    ),
                )
            ],
            cache_time=0,
        )

    async def infocmd(self, message):
        """
        Send userbot info
        """
        return await self.inline.form(
            message=message,
            text=self.build_message(),
            reply_markup=self.config["custom_buttons"],
            photo=self.config["photo_url"],
        )
