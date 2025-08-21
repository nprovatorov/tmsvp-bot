# messages.py
from textwrap import dedent
from datetime import datetime
from typing import List, Optional, Dict, Any
from .util import humanReadableSize

def _md(s: str) -> str:
    # не чiпати! Мінімальний екран для бектиків, щоб імена файлів/сигнатури не ламали Markdown
    return (s or "").replace("`", "ʼ")

# --- Адмін: старт запиту на завантаження ---
def admin_upload_started(channel_handle, filename, resolution, link, author) -> str:
    title = f"🆕 Новий запит на завантаження від #{channel_handle or 'unknown'}"
    lines = [
        title,
        f"- Файл: `{_md(filename)}`" + (f" ({resolution})" if resolution else ""),
        f"- Від: {author}",
    ]
    return "\n".join(lines)

# --- Адмін: завершення завантаження (усі кейси) ---
def admin_upload_finished(
    channel_handle: str | None,
    author: str,
    filename: str,
    resolution: str | None,
    size_h: str,
    av_status: str,          # "clean" | "infected:<sig>" | "error"
    retention_days: int,
    delete_on: datetime | None,
    description: str | None = None,
) -> str:
    title = "📥 Завантаження файлу завершено"
    lines = [title]
    lines.append(f"- Від: #{channel_handle or 'unknown'} (акаунт: {author})")
    lines.append(f"- Файл: `{_md(filename)}`" + (f" ({resolution})" if resolution else ""))
    lines.append(f"- Розмір: **{size_h}**")

    if av_status.startswith("infected:"):
        sig = av_status.split(":", 1)[1]
        lines.append(f"- Антивірус: ❌ Виявлено загрозу (`{_md(sig)}`)")
        lines.append("- Статус: файл видалено задля безпеки")
    elif av_status == "error":
        lines.append("- Антивірус: ⚠️ Помилка перевірки (файл залишено)")
        if delete_on:
            lines.append(f"- Зберігання: {retention_days} дн. · автовидалення **{delete_on:%Y-%m-%d}**")
    else:
        lines.append("- Антивірус: ✅ Чисто")
        if delete_on:
            lines.append(f"- Зберігання: {retention_days} дн. · автовидалення **{delete_on:%Y-%m-%d}**")

    if description:
        desc = description.strip()
        if len(desc) > 1500:
            desc = desc[:1500] + "…"
        lines.append("")
        lines.append("**Опис**")
        lines.append(_md(desc))

    return "\n".join(lines)

# --- Користувачеві: додано до черги ---
def file_added(path: str) -> str:
    return f"✅ Файл `{_md(path)}` додано до черги на завантаження.\nЯ повідомлю, щойно все завершиться."

# --- Користувачеві: файл вже існує (з інструкцією щодо перейменування) ---
def file_exists(path: str) -> str:
    return dedent(f"""
        ℹ️ Такий файл уже є у сховищі:
        • `{_md(path)}`
        
        **Як завантажити все ж таки?**
        — Надішліть файл ще раз із підписом `> нова_назва.ext` — ми збережемо його під новою назвою.
        **Важливо:** якщо підпис починається з `>`, увесь підпис сприймається як *назва файлу*, і опис **не буде** передано адміністратору.
    """).strip()

# --- Користувачеві: старт ---
def starting_download() -> str:
    return "▶️ Починаю завантаження…"

# (за потреби сумісності з історичним використанням)
def download_done(filename: str, total_h: str, took_h: str, speed_h: str) -> str:
    return dedent(f"""
        ✅ Готово! Файл збережено.
        • Назва: `{_md(filename)}`
        • Розмір: {total_h}
        Деталі: тривалість {took_h} • швидкість ~{speed_h}/с
    """).strip()

# --- Користувачеві: прогрес ---
def download_progress(filename: str, got_h: str, total_h: str, pct: float, speed_h: str, tte_h: str) -> str:
    return dedent(f"""
        Завантажую: `{_md(filename)}`
        **{got_h}/{total_h} ({pct:0.2f}%)**
        Швидкість: ~{speed_h}/с • лишилося {tte_h}
    """).strip()

# --- Користувачеві: зупинено (застаріле, але лишаємо) ---
def stopped(filename: str) -> str:
    return f"⏹️ Завантаження `{_md(filename)}` зупинено."

# --- Користувачеві: коли дозволено лише у публічному чаті ---
def uploads_notice_disabled() -> str:
    return "ℹ️ Завантаження приймаються лише у публічному чаті бота. Будь ласка, надішліть файл там."

# --- Адмін/приватний канал: коротке повідомлення про нове завантаження (якщо використовується) ---
def notify_new_upload(channel: str, filename: str, size_h: str, author: str) -> str:
    return dedent(f"""
        🆕 Нове завантаження з **#{channel}**
        - Файл: `{_md(filename)}`
        - Розмір: {size_h}
        - Від: {author}
    """).strip()

# --- Адмін: щотижневе використання (просте з housekeeping; детальний звіт змінюватимемо окремо) ---
def weekly_usage(total_h: str, used_h: str, free_h: str) -> str:
    return dedent(f"""
        📊 Щотижневе використання диска
        - Усього: **{total_h}**
        - Використано: **{used_h}**
        - Вільно: **{free_h}**
    """).strip()

# --- Адмін: попередження про видалення ---
def retention_warning(filename: str, age_days: int, delete_in_days: int) -> str:
    return f"⚠️ Файл `{_md(filename)}` зберігається {age_days} дн. і буде видалено через {delete_in_days} дн."

# --- Адмін: видалено за ретенцією ---
def retention_deleted(filename: str, age_days: int) -> str:
    return f"🧹 Видалено `{_md(filename)}` (вік: {age_days} дн.)."

# --- Користувачеві: успіх ---
def download_success_user(filename: str, size_h: str, time_h: str, speed_h: str) -> str:
    return (
        f"✅ Готово! Файл збережено.\n"
        f"• Назва: `{_md(filename)}`\n"
        f"• Розмір: {size_h}\n"
        f"Дякую за очікування.\n\n"
        f"Деталі: тривалість {time_h} • швидкість ~{speed_h}/с"
    )

# --- Користувачеві: інфіковано ---
def download_infected_user(filename: str, signature: str) -> str:
    return (
        "❌ На жаль, у файлі виявлено загрозу, тому його видалено для безпеки.\n"
        f"• Назва: `{_md(filename)}`\n"
        f"• Підпис: `{_md(signature)}`\n"
        "Якщо вважаєте це помилкою, надішліть іншу версію або зв’яжіться з нами."
    )

# --- Користувачеві: збій ---
def download_failed_user(filename: str) -> str:
    return (
        "❌ Не вдалося завантажити файл.\n"
        f"• Назва: `{_md(filename)}`\n"
        "Будь ласка, спробуйте ще раз або надішліть інший формат."
    )

# --- Адмін: чистий ---
def admin_download_clean(channel: str, filename: str, size_h: str, author: str) -> str:
    return (
        "✅ Файл завантажено та перевірено: чистий\n"
        f"- Файл: `{_md(filename)}` ({size_h})\n"
        f"- Звідки: #{channel} · від {author}"
    )

# --- Адмін: інфікований ---
def admin_download_infected(filename: str, signature: str) -> str:
    return f"🚨 Виявлено загрозу у файлі: `{_md(filename)}` (сигнатура: `{_md(signature)}`) — файл видалено."

# --- Адмін: помилка сканування ---
def admin_scan_error(filename: str) -> str:
    return f"⚠️ Помилка перевірки антивірусом для `{_md(filename)}`; файл залишено."

# --- Адмін: збій завантаження ---
def admin_download_crashed(filename: str) -> str:
    return f"❌ Збій під час завантаження `{_md(filename)}`."

# --- Користувачеві: скасовано ---
def download_cancelled_user(filename: str) -> str:
    name = _md(filename)
    return f"🛑 Завантаження `{name}` скасовано за вашим запитом. Файл видалено із сервера."

# --- Адмін: скасовано ---
def admin_upload_cancelled(channel_handle: str, author: str, filename: str) -> str:
    fname = _md(filename)
    title = "🛑 Запит на завантаження скасовано користувачем"
    return "\n".join([
        title,
        f"- Від: #{channel_handle or 'unknown'} (акаунт: {author})",
        f"- Файл: `{fname}`",
    ])


# --- Commands: user-facing texts (UA) ---

def start_text() -> str:
    return (
        "👋 Вітаємо!\n"
        "Надішліть файл — я збережу його на сервері.\n"
        "Щоб перейменувати під час надсилання, вкажіть підпис `> нова_назва.ext`.\n"
        "Потрібна довідка? Скористайтеся /help."
    )

def help_text() -> str:
    return (
        "📘 **Довідка**\n\n"
        "**Як це працює**\n"
        "• Надішліть файл — бот збереже його у сховище сервера.\n"
        "• Якщо файл уже існує, ви можете надіслати його знову з підписом `> нова_назва.ext`.\n\n"
        "**Перейменування**\n"
        "• Підпис, що починається з `>`, сприймається як **назва файлу** (опис не передається).\n\n"
        "**Опис файлу**\n"
        "• Звичайний підпис до файлу буде передано до адмін-каналу як опис.\n\n"
        "**Команди**\n"
        "• /start — короткий вступ\n"
        "• /help — ця довідка\n"
        "• /usage — стан сховища\n"
        "• /use `<папка>` — зберігати нові файли у вказаній підпапці\n"
        "• /leave — повернутися до кореневої папки\n"
        "• /get — показати поточну папку\n"
        "• /add `<посилання>` `[нова_назва]` — завантажити файл за посиланням на повідомлення\n"
        "• /weekly — надіслати щотижневий звіт в адмін-канал"
    )

def usage_text(total_h: str, used_h: str, free_h: str) -> str:
    return (
        "💽 **Сховище**\n"
        f"• Усього: **{total_h}**\n"
        f"• Використано: **{used_h}**\n"
        f"• Вільно: **{free_h}**"
    )

def use_need_path() -> str:
    return "Будь ласка, вкажіть підпапку, куди зберігати файли. Приклад: `/use Проєкти/Січень`"

def use_path_warning(safe_path: str, original: str) -> str:
    safe = _md(safe_path)
    orig = _md(original)
    return f"⚠️ Увага: шлях нормалізовано до `{safe}` (замість `{orig}`)."

def use_ok() -> str:
    return "✅ Гаразд, наступні файли зберігатиму в цій папці."

def leave_ok() -> str:
    return "↩️ Повернувся до кореневої папки."

def get_folder(path: str) -> str:
    return f"📂 Поточна папка: `{_md(path)}`"

def add_need_user_client() -> str:
    return "Систему бота не налаштовано для доступу до ваших повідомлень (користувацький клієнт відсутній)."

def add_need_link() -> str:
    return "Будь ласка, надішліть посилання на повідомлення."

def add_invalid_link() -> str:
    return "Невірне посилання. Перевірте формат і спробуйте ще раз."

def add_message_not_found() -> str:
    return "Не вдалося знайти повідомлення у вашому акаунті."

def add_no_media() -> str:
    return "У цьому повідомленні немає медіафайлу для завантаження."

def weekly_report_done() -> str:
    return "✅ Щотижневий звіт надіслано до адмін-каналу."

def weekly_report_failed() -> str:
    return "❌ Не вдалося сформувати щотижневий звіт."

def weekly_report_text(payload: Dict[str, Any]) -> str:
    """
    Format a weekly report using precomputed payload from metrics.py.
    payload keys (all computed in metrics.py):
      iso_year:int, iso_week:int, date_range:str,
      used:str, total:str,
      total_clean_bytes:int, wow_bytes:str,
      uploads_started:int, uploads_finished:int,
      clean_count:int, infected_count:int, cancelled_count:int, error_count:int, scan_error_count:int,
      busiest_hour: Optional[int], missing_desc_count:int,
      top_by_bytes: List[Tuple[str,int]], top_by_count: List[Tuple[str,int]],
      top_ext: List[Tuple[str,int]],
      largest_files: List[Tuple[str,int,str]],
      retention_notice_days:int, soon:int,
      deleted_files_count:int, deleted_bytes:int,
      oldest: Optional[int],
    """
    y = payload["iso_year"]
    w = payload["iso_week"]
    date_range = payload["date_range"]

    used = payload["used"]
    total = payload["total"]

    wow_bytes = payload["wow_bytes"]
    total_clean_bytes = payload["total_clean_bytes"]

    uploads_started = payload["uploads_started"]
    uploads_finished = payload["uploads_finished"]

    clean_count = payload["clean_count"]
    infected_count = payload["infected_count"]
    cancelled_count = payload["cancelled_count"]
    error_count = payload["error_count"]
    scan_error_count = payload["scan_error_count"]

    busiest_hour = payload.get("busiest_hour")
    missing_desc_count = payload.get("missing_desc_count", 0)

    top_by_bytes = payload.get("top_by_bytes", [])
    top_by_count = payload.get("top_by_count", [])
    top_ext = payload.get("top_ext", [])
    largest_files = payload.get("largest_files", [])

    retention_notice_days = payload["retention_notice_days"]
    soon = payload["soon"]
    deleted_files_count = payload["deleted_files_count"]
    deleted_bytes = payload["deleted_bytes"]
    oldest = payload.get("oldest")

    # UA bullets
    lines: List[str] = []
    lines.append(f"📊 **Щотижневий звіт бота** — ISO {y}-W{w:02d} ({date_range})")
    lines.append("")

    # Capacity
    lines.append("**Ємність**")
    lines.append(f"• Використано / Усього: {used} / {total}")
    lines.append(f"• Нових даних за тиждень: {humanReadableSize(total_clean_bytes)} ({wow_bytes})")
    lines.append("")

    # Volume
    lines.append("**Обсяг**")
    lines.append(
        "• Результати: "
        f"чистих {clean_count} • "
        f"загроз {infected_count} • "
        f"скасовано {cancelled_count} • "
        f"збоїв {error_count}"
    )
    lines.append(f"• Розпочато: {uploads_started} • Завершено: {uploads_finished}")
    if busiest_hour is not None:
        lines.append(f"• Найзавантаженіша година: {busiest_hour:02d}:00")
    if missing_desc_count:
        lines.append(f"• Без опису: {missing_desc_count}")
    lines.append("")

    # Clients
    lines.append("**Клієнти**")
    if top_by_bytes:
        txt = " • ".join([f"{k} {humanReadableSize(v)}" for k, v in top_by_bytes])
        lines.append(f"• За обсягом: {txt}")
    if top_by_count:
        txt = " • ".join([f"{k} {v}" for k, v in top_by_count])
        lines.append(f"• За кількістю: {txt}")
    new_clients = payload.get("new_clients") or []
    if new_clients:
        lines.append(f"• Нові за тиждень: {', '.join(new_clients)}")
    lines.append("")

    # File mix
    lines.append("**Типи файлів**")
    if top_ext:
        txt = " • ".join([f"{k} {v}" for k, v in top_ext])
        lines.append(f"• Найчастіші: {txt}")
    if largest_files:
        for (fn, sz, who) in largest_files:
            safe_fn = (fn or "").replace("`", "ʼ")
            lines.append(f"• Найбільший: `{safe_fn}` — {humanReadableSize(sz)} від {who}")
    lines.append("")

    # Retention
    lines.append("**Ретенція**")
    lines.append(f"• Наближається автостарт видалення (T–{retention_notice_days}д): {soon} файл(и)")
    lines.append(f"• Видалено цього тижня: {deleted_files_count} файл(и) ({humanReadableSize(deleted_bytes)})")
    if oldest is not None:
        lines.append(f"• Найстаріший збережений: {oldest} дн.")
    lines.append("")

    # Alerts
    alerts: List[str] = []
    if infected_count > 0:
        alerts.append("⚠️ Виявлено інфіковані завантаження")
    if scan_error_count > 0:
        alerts.append("⚠️ Були помилки антивірусної перевірки")
    if alerts:
        lines.append("**Попередження**")
        for a in alerts:
            lines.append(f"• {a}")
        lines.append("")

    return "\n".join(lines).strip()

def unsupported_media() -> str:
    return (
        "ℹ️ Цей тип повідомлення не підтримується.\n"
        "Будь ласка, надішліть файл як *документ* або *фотографію*. "
        "Відео, голосові, стікери та геопозицію бот не приймає."
    )