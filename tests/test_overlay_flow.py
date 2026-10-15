from __future__ import annotations

from io import BytesIO

from PIL import Image
from conftest import buttons, callback, document_message, logo_png, source_photo

from logo_bot import projects, webhook
from logo_bot.config import CHANNELS
from logo_bot.keyboards import channel_menu, delete_confirm_menu, delete_menu, option_menu, start_menu
from logo_bot.projects import all_channels, save_project, slugify
from logo_bot.state_store import UpstashStateStore, new_record_id


def upload_photo(tg) -> str:
    tg.files["photo"] = source_photo()
    webhook._handle_message(document_message("photo", mime="image/jpeg"), tg)
    first_button = buttons(tg.last_markup())[0]["callback_data"]
    return first_button.split("|")[1]


def press(tg, data: str) -> None:
    webhook._handle_callback(callback(data), tg)


def test_builtin_channel_output_is_unchanged(store, tg):
    record_id = upload_photo(tg)
    press(tg, f"ch|{record_id}|homeofhockey")
    press(tg, f"pos|{record_id}|homeofhockey|winline")

    [document] = tg.calls_of("send_document")
    assert document["filename"] == "homeofhockey_winline_4x5.png"
    assert document["caption"] == "Готово: Home of Hockey, винлайн"
    with Image.open(BytesIO(document["content"])) as result:
        assert result.size == (1080, 1350)


def test_custom_project_logo_is_downloaded_once_and_used(store, tg):
    record = save_project("Высота 3.0.5", [{"label": "Без Винлайн", "file_id": "logo1"}], "@a (1)")
    tg.files["logo1"] = logo_png()
    record_id = upload_photo(tg)
    assert buttons(tg.last_markup())[-1]["callback_data"] == f"ch|{record_id}|{record['key']}"

    press(tg, f"ch|{record_id}|{record['key']}")
    assert [b["text"] for b in buttons(tg.last_markup())] == ["Без Винлайн", "Назад к каналам"]
    press(tg, f"pos|{record_id}|{record['key']}|o1")
    press(tg, f"pos|{record_id}|{record['key']}|o1")

    documents = tg.calls_of("send_document")
    assert documents[0]["filename"] == "vysota_3_0_5_bez_vinlayn_4x5.png"
    assert documents[0]["caption"] == "Готово: Высота 3.0.5, без винлайн"
    with Image.open(BytesIO(documents[0]["content"])) as result:
        assert result.size == (1080, 1350)
        assert result.getpixel((540, 1300))[:3] == (250, 200, 0), "logo is composited at the bottom"
    assert [call["file_id"] for call in tg.calls_of("download_file")].count("logo1") == 1


def test_unknown_or_deleted_project_falls_back_to_channel_menu(store, tg):
    record_id = upload_photo(tg)
    press(tg, f"ch|{record_id}|pdeadbe")
    assert "Не нашел такой канал" in tg.last_text()


def test_menus_fit_telegram_callback_limit(store):
    record = save_project("Очень длинное название проекта на сорок", [{"label": "x" * 30, "file_id": "f"}], "@a (1)")
    record_id = new_record_id()
    markups = [channel_menu(record_id), start_menu(), delete_menu([record]), delete_confirm_menu(record["key"])]
    markups += [option_menu(record_id, channel.key) for channel in all_channels()]
    for markup in markups:
        for button in buttons(markup):
            assert len(button["callback_data"].encode("utf-8")) <= 64, button


def test_storage_failure_keeps_builtin_channels(monkeypatch):
    class BrokenStore:
        def hgetall(self, name):
            raise RuntimeError("redis is down")

    monkeypatch.setattr(projects, "get_state_store", lambda: BrokenStore())
    assert [channel.key for channel in all_channels()] == list(CHANNELS)


def test_upstash_hash_roundtrip_handles_bytes():
    class FakeRedis:
        def __init__(self):
            self.data = {}

        def hset(self, name, field, value):
            self.data.setdefault(name, {})[field] = value

        def hget(self, name, field):
            return self.data.get(name, {}).get(field)

        def hgetall(self, name):
            return {field.encode(): value.encode() for field, value in self.data.get(name, {}).items()}

    store = UpstashStateStore.__new__(UpstashStateStore)
    store.redis = FakeRedis()
    store.hset("projects:v1", "p1", {"label": "Высота"})
    assert store.hget("projects:v1", "p1") == {"label": "Высота"}
    assert store.hgetall("projects:v1") == {"p1": {"label": "Высота"}}


def test_slugify():
    assert slugify("Высота 3.0.5") == "vysota_3_0_5"
    assert slugify("С Винлайн") == "s_vinlayn"
    assert slugify("!!!") == "logo"
