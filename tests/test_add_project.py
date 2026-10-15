from __future__ import annotations

from conftest import CHAT_ID, USER_ID, buttons, callback, document_message, logo_png, photo_message, text_message

from logo_bot import webhook
from logo_bot.keyboards import channel_menu
from logo_bot.projects import PROJECTS_KEY, load_project_records, save_project


def send(tg, message) -> None:
    webhook._handle_message(message, tg)


def press(tg, data: str, user_id: int = USER_ID) -> None:
    webhook._handle_callback(callback(data, user_id=user_id), tg)


def dialog(store, user_id: int = USER_ID):
    return store.get(f"dialog:{CHAT_ID}:{user_id}")


def test_full_flow_adds_project_with_two_logos(store, tg):
    tg.files["logo1"] = logo_png()
    tg.files["logo2"] = logo_png()

    send(tg, text_message("Добавить проект"))
    assert "Как он называется" in tg.last_text()

    send(tg, text_message("  Высота   3.0.5 "))
    assert "логотип №1 для «Высота 3.0.5»" in tg.last_text()

    send(tg, document_message("logo1"))
    preview = tg.calls_of("send_photo")[-1]
    assert preview["content"][:2] == b"\xff\xd8"
    assert "Как назвать этот вариант" in preview["caption"]
    assert "не 4:5" not in preview["caption"]

    send(tg, text_message("Без Винлайн"))
    assert "Вариант 1 «Без Винлайн» принят" in tg.last_text()

    send(tg, document_message("logo2", caption="С Винлайн"))
    assert "Вариант 2 «С Винлайн» принят" in tg.last_text()
    assert load_project_records() == [], "nothing is published before «Готово»"

    press(tg, "np|done")
    assert "Проект «Высота 3.0.5» добавлен" in tg.last_text()
    assert "Без Винлайн, С Винлайн" in tg.last_text()
    assert dialog(store) is None

    [record] = load_project_records()
    assert record["label"] == "Высота 3.0.5"
    assert record["created_by"] == "@editor (7)"
    assert [(o["key"], o["label"], o["file_id"]) for o in record["options"]] == [
        ("o1", "Без Винлайн", "logo1"),
        ("o2", "С Винлайн", "logo2"),
    ]
    assert buttons(channel_menu("rec"))[-1]["text"] == "Высота 3.0.5"


def test_done_can_be_typed(store, tg):
    tg.files["logo1"] = logo_png()
    send(tg, text_message("/newproject"))
    send(tg, text_message("Высота"))
    send(tg, document_message("logo1", caption="Основной"))
    send(tg, text_message("Готово"))
    assert "Проект «Высота» добавлен" in tg.last_text()


def test_compressed_photo_is_rejected(store, tg):
    send(tg, text_message("добавить проект"))
    send(tg, text_message("Высота"))
    send(tg, photo_message("compressed"))
    assert "сжатое фото" in tg.last_text()
    assert tg.calls_of("download_file") == []
    assert dialog(store)["step"] == "logo"


def test_png_without_transparency_is_rejected(store, tg):
    tg.files["opaque"] = logo_png(transparent=False)
    send(tg, text_message("добавить проект"))
    send(tg, text_message("Высота"))
    send(tg, document_message("opaque"))
    assert "нет прозрачного фона" in tg.last_text()
    assert dialog(store)["options"] == []


def test_jpeg_is_rejected(store, tg):
    tg.files["jpeg"] = logo_png(image_format="JPEG")
    send(tg, text_message("добавить проект"))
    send(tg, text_message("Высота"))
    send(tg, document_message("jpeg", mime="image/jpeg"))
    assert "Нужен PNG" in tg.last_text()


def test_non_4x5_logo_gets_a_warning_but_is_accepted(store, tg):
    tg.files["wide"] = logo_png(size=(1080, 400))
    send(tg, text_message("добавить проект"))
    send(tg, text_message("Высота"))
    send(tg, document_message("wide", caption="Полоса"))
    assert "1080×400 — это не 4:5" in tg.calls_of("send_photo")[-1]["caption"]
    assert len(dialog(store)["options"]) == 1


def test_refuses_without_persistent_storage(store, tg):
    store.persistent = False
    send(tg, text_message("добавить проект"))
    assert "не подключено постоянное хранилище" in tg.last_text()
    assert dialog(store) is None


def test_cancel_by_text_and_button(store, tg):
    send(tg, text_message("добавить проект"))
    send(tg, text_message("Отмена"))
    assert "ничего не сохранено" in tg.last_text()
    assert dialog(store) is None

    send(tg, text_message("добавить проект"))
    press(tg, "np|cancel")
    assert "ничего не сохранено" in tg.last_text()
    assert dialog(store) is None


def test_builtin_channel_name_is_refused(store, tg):
    send(tg, text_message("добавить проект"))
    send(tg, text_message("home of hockey"))
    assert "встроенный канал" in tg.last_text()
    assert dialog(store)["step"] == "name"


def test_duplicate_option_name_is_refused(store, tg):
    tg.files["logo1"] = logo_png()
    tg.files["logo2"] = logo_png()
    send(tg, text_message("добавить проект"))
    send(tg, text_message("Высота"))
    send(tg, document_message("logo1", caption="С Винлайн"))
    send(tg, document_message("logo2", caption="с винлайн"))
    assert "уже есть в этом проекте" in tg.calls_of("send_photo")[-1]["caption"]
    assert dialog(store)["step"] == "option_name"


def test_done_without_logos_does_not_save(store, tg):
    send(tg, text_message("добавить проект"))
    send(tg, text_message("Высота"))
    send(tg, text_message("готово"))
    assert "ни одного логотипа" in tg.last_text()
    assert load_project_records() == []


def test_existing_project_gets_new_logos(store, tg):
    save_project("Высота 3.0.5", [{"label": "Без Винлайн", "file_id": "logo1"}], "@a (1)")
    tg.files["logo2"] = logo_png()

    send(tg, text_message("добавить проект"))
    send(tg, text_message("высота 3.0.5"))
    assert "уже есть" in tg.last_text()
    press(tg, "np|existing")
    assert "логотип №2" in tg.last_text()
    send(tg, document_message("logo2", caption="С Винлайн"))
    press(tg, "np|done")

    [record] = load_project_records()
    assert [o["key"] for o in record["options"]] == ["o1", "o2"]
    assert "добавлено логотипов: 1" in tg.last_text()


def test_start_command_drops_the_dialog(store, tg):
    send(tg, text_message("добавить проект"))
    send(tg, text_message("/start"))
    assert dialog(store) is None
    assert [b["callback_data"] for b in buttons(tg.last_markup())] == ["np|start", "dp|start"]


def test_dialog_of_one_user_does_not_block_another(store, tg):
    tg.files["photo"] = logo_png()
    send(tg, text_message("добавить проект", user_id=USER_ID))
    send(tg, document_message("photo", user_id=8))
    assert "Выбери канал" in tg.last_text()


def test_expired_dialog_button(store, tg):
    press(tg, "np|done")
    assert "истекло" in tg.last_text()


def test_delete_project_is_soft(store, tg):
    record = save_project("Высота", [{"label": "Основной", "file_id": "logo1"}], "@a (1)")

    send(tg, text_message("Удалить проект"))
    assert [b["callback_data"] for b in buttons(tg.last_markup())] == [f"dpc|{record['key']}", "dp|cancel"]
    press(tg, f"dpc|{record['key']}")
    assert "Удалить проект «Высота»?" in tg.last_text()
    press(tg, f"dpy|{record['key']}")
    assert "удален" in tg.last_text()

    assert load_project_records() == []
    assert [b["text"] for b in buttons(channel_menu("rec"))][-1] != "Высота"
    kept = store.hget(PROJECTS_KEY, record["key"])
    assert kept["deleted_at"] and kept["deleted_by"] == "@editor (7)"


def test_delete_with_no_custom_projects(store, tg):
    send(tg, text_message("/deleteproject"))
    assert "не добавлено ни одного проекта" in tg.last_text()


def test_deleted_name_can_be_reused(store, tg):
    record = save_project("Высота", [{"label": "Основной", "file_id": "logo1"}], "@a (1)")
    press(tg, f"dpy|{record['key']}")
    send(tg, text_message("добавить проект"))
    send(tg, text_message("Высота"))
    assert dialog(store)["step"] == "logo"
