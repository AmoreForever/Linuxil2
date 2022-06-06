"""
    ░█████╗░███╗░░░███╗░█████╗░██████╗░██████
    ██╔══██╗████╗░████║██╔══██╗██╔══██╗██╔════╝
    ███████║██╔████╔██║██║░░██║██████╔╝█████╗░░
    ██╔══██║██║╚██╔╝██║██║░░██║██╔══██╗██╔══╝░░
    ██║░░██║██║░╚═╝░██║╚█████╔╝██║░░██║███████╗
    ╚═╝░░╚═╝╚═╝░░░░░╚═╝░╚════╝░╚═╝░░╚═╝╚══════╝
           
    Copyright 2022 t.me/the_farkhodov 
    Licensed under the GNU GPLv3
"""

from .. import loader, utils
import asyncio
from datetime import datetime
import io
import json

from telethon.tl.types import Message


@loader.tds
class BackuperMod(loader.Module):
    """Backup everything and anything"""

    strings = {
        "name": "Linuxil_Backuper",
        "backup_caption": "☝️ <b>Это резервная копия вашей базы данных. Не давайте его никому, он содержит личную информацию.</b>",
        "reply_to_file": "🚫 <b>Ответить на .{} файл</b>",
        "db_restored": "🔄 <b>Обновление базы данных, перезапуск...</b>",
        "modules_backup": "🗃 <b>Бэкап модов ({})</b>",
        "notes_backup": "🗃 <b>Заметки о резервном копировании ({})</b>",
        "mods_restored": "✅ <b>Режимы восстановлены, перезапуск</b>",
        "notes_restored": "✅ <b>Заметки восстановлены</b>",
    }

    async def client_ready(self, client, db):
        self._db = db
        self._client = client

    async def backupdbcmd(self, message: Message) -> None:
        """Create database backup [will be sent in pm]"""
        txt = io.BytesIO(json.dumps(self._db).encode("utf-8"))
        txt.name = f"ftg-db-backup-{datetime.now().strftime('%d-%m-%Y-%H-%M')}.db"
        await self._client.send_file("me", txt, caption=self.strings("backup_caption"))
        await message.delete()

    async def restoredbcmd(self, message: Message) -> None:
        """Restore database from file"""
        reply = await message.get_reply_message()
        if not reply or not reply.media:
            await utils.answer(
                message, self.strings("reply_to_file", message).format("db")
            )
            await asyncio.sleep(3)
            await message.delete()
            return

        file = await message.client.download_file(reply.media)
        decoded_text = json.loads(file.decode("utf-8"))
        self._db.clear()
        self._db.update(**decoded_text)
        self._db.save()
        await utils.answer(message, self.strings("db_restored", message))
        await self.allmodules.commands["restart"](await message.respond("_"))

    async def backupmodscmd(self, message: Message) -> None:
        """Create backup of mods"""
        data = json.dumps(
            {
                "loaded": self._db.get(
                    "friendly-telegram.modules.loader", "loaded_modules", []
                ),
                "unloaded": [],
            }
        )
        txt = io.BytesIO(data.encode("utf-8"))
        txt.name = f"linuxil-mods-{datetime.now().strftime('%d-%m-%Y-%H-%M')}.mods"
        await self._client.send_file(
            utils.get_chat_id(message),
            txt,
            caption=self.strings("modules_backup", message).format(
                len(
                    self._db.get(
                        "friendly-telegram.modules.loader", "loaded_modules", []
                    )
                )
            ),
        )
        await message.delete()

    async def restoremodscmd(self, message: Message) -> None:
        """<reply to file> - Restore mods from backup"""
        reply = await message.get_reply_message()
        if not reply or not reply.media:
            await utils.answer(
                message, self.strings("reply_to_file", message).format("mods")
            )
            await asyncio.sleep(3)
            await message.delete()
            return

        file = await message.client.download_file(reply.media)
        decoded_text = json.loads(file.decode("utf-8"))
        self._db.set(
            "friendly-telegram.modules.loader", "loaded_modules", decoded_text["loaded"]
        )
        self._db.set(
            "friendly-telegram.modules.loader",
            "unloaded_modules",
            decoded_text["unloaded"],
        )
        self._db.save()
        await utils.answer(message, self.strings("mods_restored", message))
        await self.allmodules.commands["restart"](await message.respond("_"))

    async def backupnotescmd(self, message: Message) -> None:
        """Create the backup of notes"""
        data = json.dumps(self._db.get("friendly-telegram.modules.notes", "notes", []))
        txt = io.BytesIO(data.encode("utf-8"))
        txt.name = f"ftg-notes-{datetime.now().strftime('%d-%m-%Y-%H-%M')}.notes"
        await self._client.send_file(
            utils.get_chat_id(message),
            txt,
            caption=self.strings("notes_backup", message).format(
                len(self._db.get("friendly-telegram.modules.notes", "notes", []))
            ),
        )
        await message.delete()

    async def restorenotescmd(self, message: Message) -> None:
        """<reply to file> - Restore notes from backup"""
        reply = await message.get_reply_message()
        if not reply or not reply.media:
            await utils.answer(
                message, self.strings("reply_to_file", message).format("notes")
            )
            await asyncio.sleep(3)
            await message.delete()
            return

        file = await message.client.download_file(reply.media)
        decoded_text = json.loads(file.decode("utf-8"))
        self._db.set("friendly-telegram.modules.notes", "notes", decoded_text)
        self._db.save()
        await utils.answer(message, self.strings("notes_restored", message))
