import logging
import re
import time
from typing import List

import requests

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_CHARS = 4096
_CHUNK_DELAY = 0.5


def _md_to_html(text: str) -> str:
    # Escape HTML-significant chars in data first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # ## heading
    text = re.sub(r"^## (.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    # **bold**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # * bullet
    text = re.sub(r"^\* (.+)$", r"• \1", text, flags=re.MULTILINE)
    # > blockquote (after escaping, > becomes &gt;)
    text = re.sub(r"^&gt; (.+)$", r"<i>\1</i>", text, flags=re.MULTILINE)
    # --- horizontal rule
    text = re.sub(r"^---$", "", text, flags=re.MULTILINE)
    return text.strip()


def _split_into_chunks(text: str, max_chars: int = _MAX_CHARS) -> List[str]:
    # Split before lines starting with 【 or ===
    parts = re.split(r"(?=^(?:【|===))", text, flags=re.MULTILINE)
    parts = [p.strip() for p in parts if p.strip()]

    chunks: List[str] = []
    for part in parts:
        if len(part) <= max_chars:
            chunks.append(part)
        else:
            paragraphs = re.split(r"\n{2,}", part)
            current = ""
            for para in paragraphs:
                candidate = (current + "\n\n" + para).strip() if current else para
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    if len(para) > max_chars:
                        for i in range(0, len(para), max_chars):
                            chunks.append(para[i : i + max_chars])
                        current = ""
                    else:
                        current = para
            if current:
                chunks.append(current)

    return chunks


def send_report(
    report: str,
    bot_token: str,
    chat_id: str,
    proxy_url: str | None = None,
) -> bool:
    html_report = _md_to_html(report)
    chunks = _split_into_chunks(html_report)
    plain_chunks = _split_into_chunks(report)
    url = _TELEGRAM_API.format(token=bot_token)
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    all_ok = True
    for i, chunk in enumerate(chunks, 1):
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"}
        for attempt_proxies in ([proxies, None] if proxies else [None]):
            try:
                resp = requests.post(url, json=payload, proxies=attempt_proxies, timeout=15)
                resp.raise_for_status()
                if attempt_proxies is None and proxies is not None:
                    logger.warning("Telegram: 第 %d 条代理不可用，已直连发送", i)
                else:
                    logger.info("Telegram: 已发送第 %d/%d 条", i, len(chunks))
                break
            except requests.HTTPError:
                try:
                    tg_error = resp.json().get("description", "")
                except Exception:
                    tg_error = ""
                logger.error("Telegram: 第 %d 条发送失败（HTTP）: %s", i, tg_error)
                if "can't parse" in tg_error.lower() or "bad request" in tg_error.lower():
                    logger.warning("Telegram: HTML 解析失败，回退纯文本重试")
                    plain_payload = {
                        "chat_id": chat_id,
                        "text": plain_chunks[i - 1] if i - 1 < len(plain_chunks) else chunk,
                    }
                    try:
                        resp2 = requests.post(url, json=plain_payload, proxies=attempt_proxies, timeout=15)
                        resp2.raise_for_status()
                        logger.info("Telegram: 第 %d 条（纯文本）发送成功", i)
                    except Exception as e2:
                        logger.error("Telegram: 纯文本重试失败: %s", e2)
                        all_ok = False
                else:
                    all_ok = False
                break
            except requests.RequestException as e:
                if attempt_proxies is not None:
                    logger.warning("Telegram: 第 %d 条代理连接失败，尝试直连: %s", i, e)
                    continue
                logger.error("Telegram: 第 %d 条网络异常: %s", i, e)
                all_ok = False

        if i < len(chunks):
            time.sleep(_CHUNK_DELAY)

    return all_ok
