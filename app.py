import os
import re
import hmac
import time
import uuid
import json
import shutil
import hashlib
import sqlite3
import mimetypes
import threading
from urllib.parse import urlparse
from functools import wraps
from datetime import datetime
from flask import (
    Flask, render_template, request, jsonify,
    session, send_file, abort, Response
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'educraft.db')
UPLOAD_PDF_DIR = os.path.join(BASE_DIR, 'uploads', 'pdfs')
UPLOAD_HTML_DIR = os.path.join(BASE_DIR, 'uploads', 'html')
UPLOAD_VIDEO_DIR = os.path.join(BASE_DIR, 'uploads', 'videos')
UPLOAD_IMAGE_DIR = os.path.join(BASE_DIR, 'uploads', 'images')
UPLOAD_RECORDING_DIR = os.path.join(BASE_DIR, 'uploads', 'recordings')

ALLOWED_VIDEO_EXTS = {'.mp4', '.webm', '.mov', '.m4v', '.ogg', '.ogv'}
ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'}
ALLOWED_RECORDING_EXTS = {'.webm', '.mp4', '.mkv', '.mov', '.ogg'}

DEFAULT_DESIGN = {
    'fontFamily': 'Inter',
    'pageBg': '#f8fafc',
    'cardBg': '#ffffff',
    'textColor': '#0f172a',
    'headerBg': '#ffffff',
    'footerBg': '#0f172a',
    'useCustomHeroGradient': False,
    'heroBgStart': '#0f172a',
    'heroBgEnd': '#312e81',
    'heroTextColor': '#ffffff',
    'heroAlign': 'left',
    'heroPadding': 'normal',
    'useCustomAccent': False,
    'customAccentHex': '#4f46e5',
    'containerWidth': 'normal',
    'borderRadius': 'rounded',
    'cardShadow': 'soft',
    'catalogColumns': 3,
    'logoImage': '',
    'logoHeight': 36,
}

os.makedirs(UPLOAD_PDF_DIR, exist_ok=True)
os.makedirs(UPLOAD_HTML_DIR, exist_ok=True)
os.makedirs(UPLOAD_VIDEO_DIR, exist_ok=True)
os.makedirs(UPLOAD_IMAGE_DIR, exist_ok=True)
os.makedirs(UPLOAD_RECORDING_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'educraft-dev-secret-key-change-in-prod-2026')
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # Лимит загрузки файлов (включая видео и записи): 1 ГБ


# =========================================================================
# РАБОТА С БАЗОЙ ДАННЫХ SQLITE
# =========================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def generate_built_in_demo_pdf_bytes() -> bytes:
    """Генерирует валидный 3-страничный демо-PDF для предустановленного урока."""
    pages_content = [
        '\n'.join([
            'BT /F2 20 Tf 50 760 Td (VECTOR ACADEMY - UX/UI DESIGN GUIDE) Tj ET',
            'BT /F1 12 Tf 50 732 Td (Module 1, Lesson 3: Modular Grids, Typography & Visual Hierarchy) Tj ET',
            '0.85 0.87 0.92 RG 50 718 m 545 718 l S',
            'BT /F2 14 Tf 50 685 Td (1. Core Principles of Web Typography) Tj ET',
            'BT /F1 11 Tf 50 662 Td (Typography represents up to 85% of any educational interface.) Tj ET',
            'BT /F1 11 Tf 50 644 Td (A well-structured type scale turns complex lectures into clear guides:) Tj ET',
            'BT /F1 11 Tf 65 620 Td (- Optimal line length: 55 to 75 characters per line.) Tj ET',
            'BT /F1 11 Tf 65 602 Td (- Body text line-height: 1.45 to 1.65 relative to font size.) Tj ET',
            'BT /F1 11 Tf 65 584 Td (- Contrast ratio: minimum 4.5:1 according to WCAG AA standard.) Tj ET',
            'BT /F2 14 Tf 50 545 Td (2. The 8-Point Grid System) Tj ET',
            'BT /F1 11 Tf 50 522 Td (Use multiples of 8px (8, 16, 24, 32, 48, 64) for all paddings,) Tj ET',
            'BT /F1 11 Tf 50 504 Td (margins, card gaps, and button heights across desktop and mobile.) Tj ET',
            'BT /F1 10 Tf 50 60 Td (Protected Course Material - Page 1 of 3) Tj ET',
        ]),
        '\n'.join([
            'BT /F2 18 Tf 50 760 Td (VISUAL HIERARCHY & RESPONSIVE BREAKPOINTS) Tj ET',
            '0.85 0.87 0.92 RG 50 744 m 545 744 l S',
            'BT /F2 14 Tf 50 710 Td (3. Three Levels of Visual Attention) Tj ET',
            'BT /F1 11 Tf 50 686 Td (Level 1 (Primary): Course title, main CTA button, key value metric.) Tj ET',
            'BT /F1 11 Tf 50 668 Td (Level 2 (Secondary): Module subtitles, lesson duration, category tags.) Tj ET',
            'BT /F1 11 Tf 50 650 Td (Level 3 (Tertiary): Footnotes, metadata, secondary borders.) Tj ET',
            'BT /F2 14 Tf 50 610 Td (4. Standard Responsive Grid Columns) Tj ET',
            'BT /F1 11 Tf 65 586 Td (* Desktop (1280px+): 12-column grid, 24px-32px gutter.) Tj ET',
            'BT /F1 11 Tf 65 568 Td (* Tablet (768px-1024px): 8-column grid, 20px gutter.) Tj ET',
            'BT /F1 11 Tf 65 550 Td (* Mobile (360px-480px): 4-column grid, 16px side margins.) Tj ET',
            'BT /F1 10 Tf 50 60 Td (Protected Course Material - Page 2 of 3) Tj ET',
        ]),
        '\n'.join([
            'BT /F2 18 Tf 50 760 Td (PRACTICAL ASSIGNMENT & CHECKLIST) Tj ET',
            '0.85 0.87 0.92 RG 50 744 m 545 744 l S',
            'BT /F2 14 Tf 50 710 Td (Homework Task for Lesson 3) Tj ET',
            'BT /F1 11 Tf 50 686 Td (1. Create a modular typographic scale in Figma (H1, H2, H3, Body, Caption).) Tj ET',
            'BT /F1 11 Tf 50 668 Td (2. Configure a 12-column desktop frame (1440px) with 80px margins.) Tj ET',
            'BT /F1 11 Tf 50 650 Td (3. Design a course catalog card following the 8pt spacing rule.) Tj ET',
            'BT /F1 11 Tf 50 632 Td (4. Verify text contrast using a contrast checker plugin.) Tj ET',
            'BT /F2 12 Tf 50 585 Td (Security Notice: Unauthorized copying or distribution is prohibited.) Tj ET',
            'BT /F1 10 Tf 50 60 Td (Protected Course Material - Page 3 of 3) Tj ET',
        ]),
    ]

    objects = [None] * 11
    objects[1] = '<< /Type /Catalog /Pages 2 0 R >>'
    objects[2] = '<< /Type /Pages /Kids [5 0 R 7 0 R 9 0 R] /Count 3 >>'
    objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
    objects[4] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>'

    for i, stream_str in enumerate(pages_content):
        page_obj_num = 5 + i * 2
        content_obj_num = 6 + i * 2
        objects[page_obj_num] = (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
            f'/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_obj_num} 0 R >>'
        )
        objects[content_obj_num] = f'<< /Length {len(stream_str)} >>\nstream\n{stream_str}\nendstream'

    pdf = '%PDF-1.4\n'
    offsets = [0] * len(objects)
    for i in range(1, len(objects)):
        offsets[i] = len(pdf)
        pdf += f'{i} 0 obj\n{objects[i]}\nendobj\n'

    xref_offset = len(pdf)
    pdf += f'xref\n0 {len(objects)}\n'
    pdf += '0000000000 65535 f \n'
    for i in range(1, len(objects)):
        pdf += f'{str(offsets[i]).zfill(10)} 00000 n \n'
    pdf += f'trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF'

    return pdf.encode('utf-8')


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            school_name TEXT NOT NULL,
            hero_title TEXT NOT NULL,
            hero_subtitle TEXT NOT NULL,
            hero_cta_text TEXT NOT NULL,
            accent_color TEXT NOT NULL DEFAULT 'indigo',
            contact_email TEXT NOT NULL,
            contact_telegram TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            protect_watermark INTEGER NOT NULL DEFAULT 1,
            protect_blur INTEGER NOT NULL DEFAULT 1,
            protect_shortcuts INTEGER NOT NULL DEFAULT 1,
            sbp_qr_image TEXT NOT NULL DEFAULT '',
            design_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS courses (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER NOT NULL DEFAULT 0,
            cover_gradient TEXT NOT NULL DEFAULT 'grad-indigo',
            cover_image TEXT NOT NULL DEFAULT '',
            short_description TEXT NOT NULL DEFAULT '',
            full_description TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS lessons (
            id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL,
            duration TEXT NOT NULL DEFAULT '20 мин',
            is_free INTEGER NOT NULL DEFAULT 0,
            video_url TEXT NOT NULL DEFAULT '',
            content_type TEXT NOT NULL DEFAULT 'text',
            pdf_filename TEXT NOT NULL DEFAULT '',
            pdf_stored_name TEXT NOT NULL DEFAULT '',
            html_filename TEXT NOT NULL DEFAULT '',
            html_stored_name TEXT NOT NULL DEFAULT '',
            video_filename TEXT NOT NULL DEFAULT '',
            video_stored_name TEXT NOT NULL DEFAULT '',
            enable_code_tab INTEGER NOT NULL DEFAULT 0,
            content TEXT NOT NULL DEFAULT '',
            default_html TEXT NOT NULL DEFAULT '',
            default_css TEXT NOT NULL DEFAULT '',
            default_js TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            user_id TEXT NOT NULL,
            course_id TEXT NOT NULL,
            purchased_at TEXT NOT NULL,
            PRIMARY KEY (user_id, course_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lesson_progress (
            user_id TEXT NOT NULL,
            lesson_id TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, lesson_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS homework_submissions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            lesson_id TEXT NOT NULL,
            answer_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'submitted',
            submitted_at TEXT NOT NULL,
            UNIQUE (user_id, lesson_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS page_photos (
            id TEXT PRIMARY KEY,
            image_url TEXT NOT NULL,
            stored_name TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            caption TEXT NOT NULL DEFAULT '',
            page_target TEXT NOT NULL DEFAULT 'catalog',
            target_entity_id TEXT NOT NULL DEFAULT '',
            placement TEXT NOT NULL DEFAULT 'after_hero',
            align TEXT NOT NULL DEFAULT 'center',
            width_preset TEXT NOT NULL DEFAULT 'medium',
            height_px INTEGER NOT NULL DEFAULT 0,
            object_fit TEXT NOT NULL DEFAULT 'cover',
            rounded TEXT NOT NULL DEFAULT 'xl',
            layout_mode TEXT NOT NULL DEFAULT 'card',
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_visible INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS conferences (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            course_id TEXT NOT NULL DEFAULT '',
            host_user_id TEXT NOT NULL DEFAULT '',
            scheduled_at TEXT NOT NULL DEFAULT '',
            max_participants INTEGER NOT NULL DEFAULT 50,
            engine TEXT NOT NULL DEFAULT 'builtin',
            sfu_domain TEXT NOT NULL DEFAULT 'meet.ffmuc.net',
            room_code TEXT NOT NULL DEFAULT '',
            access_pin TEXT NOT NULL DEFAULT '',
            allow_recording INTEGER NOT NULL DEFAULT 1,
            mute_on_entry INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'scheduled',
            created_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS conference_recordings (
            id TEXT PRIMARY KEY,
            conference_id TEXT NOT NULL,
            title TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            file_size INTEGER NOT NULL DEFAULT 0,
            duration_sec INTEGER NOT NULL DEFAULT 0,
            recorded_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (conference_id) REFERENCES conferences(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS conference_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conference_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            user_role TEXT NOT NULL DEFAULT 'student',
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conference_id) REFERENCES conferences(id) ON DELETE CASCADE
        );
    """)

    # Безопасная миграция для существующей БД без колонок html_filename / html_stored_name
    cols = [row['name'] for row in cur.execute('PRAGMA table_info(lessons)').fetchall()]
    if 'html_filename' not in cols:
        cur.execute("ALTER TABLE lessons ADD COLUMN html_filename TEXT NOT NULL DEFAULT ''")
    if 'html_stored_name' not in cols:
        cur.execute("ALTER TABLE lessons ADD COLUMN html_stored_name TEXT NOT NULL DEFAULT ''")
    if 'video_filename' not in cols:
        cur.execute("ALTER TABLE lessons ADD COLUMN video_filename TEXT NOT NULL DEFAULT ''")
    if 'video_stored_name' not in cols:
        cur.execute("ALTER TABLE lessons ADD COLUMN video_stored_name TEXT NOT NULL DEFAULT ''")
    s_cols = [row['name'] for row in cur.execute('PRAGMA table_info(settings)').fetchall()]
    if 'sbp_qr_image' not in s_cols:
        cur.execute("ALTER TABLE settings ADD COLUMN sbp_qr_image TEXT NOT NULL DEFAULT ''")
    if 'design_json' not in s_cols:
        cur.execute("ALTER TABLE settings ADD COLUMN design_json TEXT NOT NULL DEFAULT '{}'")

    existing = cur.execute('SELECT COUNT(*) AS cnt FROM settings').fetchone()['cnt']
    if existing == 0:
        cur.execute("""
            INSERT INTO settings (
                id, school_name, hero_title, hero_subtitle, hero_cta_text,
                accent_color, contact_email, contact_telegram, contact_phone,
                protect_watermark, protect_blur, protect_shortcuts, sbp_qr_image
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1, '')
        """, (
            'Академия Профессий «Вектор»',
            'Освойте востребованные навыки будущего на практике',
            'Авторские онлайн-курсы с проверкой заданий, закрытыми методическими материалами и бессрочным доступом в личном кабинете.',
            'Выбрать программу обучения',
            'indigo',
            'hello@vector-academy.ru',
            '@vector_school_support',
            '+7 (495) 128-44-90'
        ))

        cur.execute(
            'INSERT INTO users (id, name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            ('user-admin', 'Алексей Смирнов (Автор школы)', 'admin@vector.ru', generate_password_hash('admin'), 'admin', '2026-01-10')
        )
        cur.execute(
            'INSERT INTO users (id, name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            ('user-student', 'Мария Соколова', 'student@vector.ru', generate_password_hash('123'), 'student', '2026-02-14')
        )

        courses_seed = [
            (
                'course-1',
                'Основы UX/UI дизайна: от прототипа до дизайн-системы',
                'Дизайн',
                14900,
                'grad-indigo',
                '',
                'Научитесь проектировать удобные интерфейсы в Figma, проводить пользовательские исследования и собирать масштабируемые дизайн-системы.',
                'Практический курс для начинающих дизайнеров и продакт-менеджеров. Вы пройдете полный цикл создания цифрового продукта: от глубинных интервью с пользователями и проектирования пользовательских сценариев (User Flow) до интерактивного прототипирования, типографики, работы с сетками и передачи макетов в разработку.'
            ),
            (
                'course-2',
                'Современный Frontend на JavaScript и Tailwind CSS',
                'Разработка',
                19900,
                'grad-emerald',
                '',
                'Создание быстрых адаптивных веб-приложений, работа с DOM, асинхронными запросами и локальным хранилищем.',
                'Пошаговый курс по современной веб-разработке без лишней теории. Вы научитесь верстать сложные адаптивные интерфейсы, управлять состоянием приложения и интегрировать фронтенд с REST API на Python.'
            ),
            (
                'course-3',
                'Запуск и монетизация онлайн-школы: от идеи до первых продаж',
                'Маркетинг',
                12500,
                'grad-amber',
                '',
                'Упаковка образовательной программы, линейка тарифов, прогрев аудитории и защита авторского контента.',
                'Практическое руководство для экспертов и методистов по запуску собственных образовательных продуктов, настройке воронки продаж и повышению доходимости учеников до конца курса.'
            )
        ]
        cur.executemany(
            'INSERT INTO courses VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            courses_seed
        )

        demo_pdf_stored = 'demo_typography.pdf'
        demo_pdf_path = os.path.join(UPLOAD_PDF_DIR, demo_pdf_stored)
        if not os.path.exists(demo_pdf_path):
            with open(demo_pdf_path, 'wb') as f:
                f.write(generate_built_in_demo_pdf_bytes())

        lessons_seed = [
            (
                'lesson-1-1', 'course-1', 1,
                'Введение в UX-исследования и анализ целевой аудитории',
                '24 мин', 1, '', 'text', '', '', '', '', 0,
                'Пользовательский опыт (UX) начинается задолго до открытия графического редактора. Главная ошибка начинающих дизайнеров — попытка сразу рисовать красивые экраны без понимания реальных задач и болей пользователя.\n\n1. Что такое JTBD (Jobs To Be Done)\nФреймворк «Работа, которая должна быть выполнена» помогает сместить фокус с социально-демографических характеристик на контекст ситуации.\n\n2. Правила проведения глубинного интервью:\n— Задавайте открытые вопросы о прошлом опыте.\n— Не подсказывайте ответы и не защищайте свой интерфейс.\n— Фиксируйте барьеры и моменты непонимания терминологии.',
                '', '', ''
            ),
            (
                'lesson-1-2', 'course-1', 2,
                'Информационная архитектура и проектирование User Flow',
                '32 мин', 0, '', 'text', '', '', '', '', 0,
                'Информационная архитектура определяет, как контент сгруппирован, назван и связан между собой. Хорошая архитектура позволяет пользователю интуитивно находить нужный раздел за 2–3 клика.',
                '', '', ''
            ),
            (
                'lesson-1-3', 'course-1', 3,
                'Модульные сетки, типографика и визуальная иерархия',
                '40 мин', 0, '', 'pdf', 'Методичка_Сетки_и_Типографика.pdf', demo_pdf_stored, '', '', 0,
                'Типографика составляет до 85% любого контентного интерфейса. Изучите прикрепленную защищенную методичку в формате PDF ниже.',
                '', '', ''
            ),
            (
                'lesson-1-4', 'course-1', 4,
                'Практикум: верстка интерактивной карточки тарифа (HTML/CSS/JS)',
                '45 мин', 1, '', 'code', '', '', '', '', 1,
                'В этом практическом уроке вы создадите интерактивную карточку тарифа онлайн-курса с переключением формата обучения и мгновенным расчетом стоимости. Переключитесь на вкладку «Песочница кода».',
                '<div class="landing">\n  <span class="badge">Интенсив 2026</span>\n  <h1>Проектирование интерфейсов с нуля</h1>\n  <p>Практический курс с проверкой домашних заданий.</p>\n  <div class="tariffs">\n    <button class="tariff active" data-price="14900">Базовый — 14 900 ₽</button>\n    <button class="tariff" data-price="24900">С наставником — 24 900 ₽</button>\n  </div>\n  <button id="enrollBtn" class="cta">Записаться за 14 900 ₽</button>\n  <div id="statusMsg" class="status"></div>\n</div>',
                'body { background: #0f172a; color: #f8fafc; font-family: system-ui, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }\n.landing { max-width: 600px; background: #1e293b; border: 1px solid #334155; border-radius: 20px; padding: 36px; text-align: center; }\n.badge { background: rgba(99,102,241,0.2); color: #a5b4fc; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 600; }\n.tariffs { display: flex; gap: 10px; justify-content: center; margin: 20px 0; }\n.tariff { background: #0f172a; color: #cbd5e1; border: 1px solid #334155; padding: 10px 16px; border-radius: 10px; cursor: pointer; }\n.tariff.active { border-color: #6366f1; color: #fff; }\n.cta { background: #6366f1; color: #fff; border: none; padding: 12px 24px; border-radius: 10px; font-weight: 700; cursor: pointer; }\n.status { margin-top: 14px; color: #34d399; font-weight: 600; }',
                'const tariffs = document.querySelectorAll(".tariff");\nconst enrollBtn = document.getElementById("enrollBtn");\nconst statusMsg = document.getElementById("statusMsg");\nlet price = "14 900 ₽";\ntariffs.forEach(b => b.addEventListener("click", () => {\n  tariffs.forEach(x => x.classList.remove("active"));\n  b.classList.add("active");\n  price = Number(b.dataset.price).toLocaleString("ru-RU") + " ₽";\n  enrollBtn.textContent = "Записаться за " + price;\n}));\nenrollBtn.addEventListener("click", () => {\n  statusMsg.textContent = "Заявка оформлена! Тариф: " + price;\n});'
            ),
            (
                'lesson-2-1', 'course-2', 1,
                'Архитектура SPA и интеграция с Python REST API',
                '35 мин', 1, '', 'code', '', '', '', '', 1,
                'Современные веб-приложения разделяют интерфейс и серверную логику через JSON API на Python (Flask/FastAPI).',
                '<h2>Тест API запроса</h2>\n<button id="pingBtn">Проверить статус сервера</button>\n<pre id="out"></pre>',
                'body { font-family: sans-serif; padding: 24px; background: #f8fafc; }\nbutton { background: #059669; color: white; border: none; padding: 10px 18px; border-radius: 8px; cursor: pointer; }',
                'document.getElementById("pingBtn").onclick = () => {\n  document.getElementById("out").textContent = "Статус: Python Flask Backend активен!";\n};'
            ),
            (
                'lesson-2-2', 'course-2', 2,
                'Асинхронный JavaScript: Promise, async/await и Fetch API',
                '42 мин', 0, '', 'text', '', '', '', '', 0,
                'Работа с внешними API требует корректной обработки состояний загрузки (Loading), успешного ответа (Success) и сетевых ошибок (Error) через блоки try / catch.',
                '', '', ''
            ),
            (
                'lesson-3-1', 'course-3', 1,
                'Проектирование продуктовой матрицы и бесплатного вводного урока',
                '28 мин', 1, '', 'text', '', '', '', '', 0,
                'Бесплатный первый урок — лучший инструмент демонстрации экспертности. Он должен давать ученику быстрый измеримый результат уже за первые 20 минут обучения.',
                '', '', ''
            ),
            (
                'lesson-3-2', 'course-3', 2,
                'Юридическая и техническая защита авторских курсов от сливов',
                '30 мин', 0, '', 'text', '', '', '', '', 0,
                'Комбинация серверной проверки прав доступа, персонализированных водяных знаков с email покупателя и постраничного рендеринга PDF снижает риск несанкционированного распространения материалов.',
                '', '', ''
            )
        ]
        cur.executemany(
            """INSERT INTO lessons (
                id, course_id, sort_order, title, duration, is_free, video_url,
                content_type, pdf_filename, pdf_stored_name, html_filename, html_stored_name,
                enable_code_tab, content, default_html, default_css, default_js
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            lessons_seed
        )

        now_str = datetime.now().strftime('%Y-%m-%d')
        cur.executemany(
            'INSERT INTO enrollments (user_id, course_id, purchased_at) VALUES (?, ?, ?)',
            [
                ('user-admin', 'course-1', now_str),
                ('user-admin', 'course-2', now_str),
                ('user-admin', 'course-3', now_str),
                ('user-student', 'course-1', now_str),
            ]
        )
        cur.execute(
            'INSERT INTO lesson_progress (user_id, lesson_id, completed_at) VALUES (?, ?, ?)',
            ('user-student', 'lesson-1-1', now_str)
        )

    conn.commit()
    conn.close()


# =========================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ АВТОРИЗАЦИИ И ПРАВ ДОСТУПА
# =========================================================================

def get_current_user(conn):
    user_id = session.get('user_id')
    if not user_id:
        return None
    row = conn.execute('SELECT id, name, email, role, created_at FROM users WHERE id = ?', (user_id,)).fetchone()
    return dict(row) if row else None


def has_lesson_access(conn, user, lesson_row) -> bool:
    """Серверная проверка: доступен ли урок пользователю."""
    if bool(lesson_row['is_free']):
        return True
    if not user:
        return False
    if user['role'] == 'admin':
        return True
    enrolled = conn.execute(
        'SELECT 1 FROM enrollments WHERE user_id = ? AND course_id = ?',
        (user['id'], lesson_row['course_id'])
    ).fetchone()
    return enrolled is not None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Требуется авторизация'}), 401
        conn = get_db()
        user = conn.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        if not user or user['role'] != 'admin':
            return jsonify({'error': 'Доступ разрешён только администратору школы'}), 403
        return f(*args, **kwargs)
    return wrapper




def get_watermark_label(user) -> str:
    """Формирует персональную метку водяного знака для защищённого просмотра."""
    if user:
        return f"{user['email']} • ID:{user['id']}"
    return 'Защищённый просмотр'


def generate_video_token(lesson_id: str, user_id: str, ttl_seconds: int = 7200) -> str:
    """Генерирует краткосрочный HMAC-токен для защищённого стриминга видеофайла."""
    exp = int(time.time()) + ttl_seconds
    uid = user_id or 'guest'
    payload = f"{lesson_id}:{uid}:{exp}"
    sig = hmac.new(
        app.secret_key.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:32]
    return f"{exp}.{sig}"


def verify_video_token(token: str, lesson_id: str, user_id: str) -> bool:
    """Проверяет подпись и срок действия токена воспроизведения видео."""
    if not token or '.' not in token:
        return False
    parts = token.split('.', 1)
    try:
        exp = int(parts[0])
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    uid = user_id or 'guest'
    payload = f"{lesson_id}:{uid}:{exp}"
    expected_sig = hmac.new(
        app.secret_key.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:32]
    return hmac.compare_digest(parts[1], expected_sig)


def build_page_protection_snippet(watermark_label: str, is_pdf_viewer: bool = False) -> str:
    """Генерирует усиленный защитный слой от копирования, скачивания, печати и скриншотов."""
    wm_json = json.dumps(watermark_label, ensure_ascii=False)
    allow_inputs_js = 'false' if is_pdf_viewer else 'true'
    img_pointer_css = 'pointer-events: none !important;' if is_pdf_viewer else ''
    wm_color = '#ffffff' if is_pdf_viewer else '#0f172a'
    return f"""
<!-- EduCraft Content & Anti-Screenshot Protection Layer -->
<style id="sec-protect-style">
  html, body, body * {{
    -webkit-user-select: none !important;
    -moz-user-select: none !important;
    -ms-user-select: none !important;
    user-select: none !important;
    -webkit-touch-callout: none !important;
  }}
  input, textarea, select, [contenteditable="true"] {{
    -webkit-user-select: text !important;
    -moz-user-select: text !important;
    -ms-user-select: text !important;
    user-select: text !important;
  }}
  img, canvas, svg, video {{
    -webkit-user-drag: none !important;
    user-drag: none !important;
    {img_pointer_css}
  }}
  /* Мгновенное полное скрытие контента при срабатывании защиты от скриншота */
  body.sec-screen-blocked > *:not(#sec-protect-curtain):not(#sec-protect-toast) {{
    visibility: hidden !important;
    opacity: 0 !important;
    filter: blur(28px) !important;
  }}
  #sec-protect-watermark {{
    position: fixed !important;
    inset: -24px !important;
    z-index: 2147483645 !important;
    pointer-events: none !important;
    overflow: hidden !important;
    display: grid !important;
    grid-template-columns: repeat(3, 1fr) !important;
    align-items: center !important;
    justify-items: center !important;
    gap: 52px !important;
    padding: 36px !important;
    opacity: 0.13 !important;
    transition: transform 0.6s ease !important;
  }}
  #sec-protect-watermark span {{
    transform: rotate(-26deg) !important;
    font: 700 13px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    color: {wm_color} !important;
    white-space: nowrap !important;
    letter-spacing: 0.02em !important;
  }}
  #sec-protect-curtain {{
    position: fixed !important;
    inset: 0 !important;
    z-index: 2147483647 !important;
    background: #020617 !important;
    color: #f8fafc !important;
    display: none;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    padding: 24px !important;
    font: 600 18px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
  }}
  #sec-protect-curtain.active {{
    display: flex !important;
  }}
  #sec-protect-curtain .sec-shield-badge {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #fda4af;
    background: rgba(244, 63, 94, 0.16);
    border: 1px solid rgba(244, 63, 94, 0.4);
    padding: 4px 12px;
    border-radius: 999px;
    margin-bottom: 14px;
  }}
  #sec-protect-curtain small {{
    margin-top: 8px;
    font-size: 13px;
    font-weight: 400;
    color: #94a3b8;
    max-width: 460px;
  }}
  #sec-protect-toast {{
    position: fixed !important;
    bottom: 20px !important;
    right: 20px !important;
    z-index: 2147483646 !important;
    background: rgba(15, 23, 42, 0.96) !important;
    color: #f8fafc !important;
    border: 1px solid rgba(248, 113, 113, 0.5) !important;
    border-radius: 12px !important;
    padding: 10px 16px !important;
    font: 600 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.4) !important;
    opacity: 0;
    pointer-events: none !important;
    transition: opacity 0.2s ease !important;
  }}
  #sec-protect-toast.visible {{
    opacity: 1 !important;
  }}
  @media print {{
    html, body, body * {{
      display: none !important;
      visibility: hidden !important;
    }}
    html::after {{
      content: "Печать, сохранение и копирование защищённых материалов курса запрещены системой безопасности.";
      display: block !important;
      visibility: visible !important;
      padding: 48px !important;
      text-align: center !important;
      font: 700 20px/1.5 sans-serif !important;
      color: #0f172a !important;
    }}
  }}
</style>
<script id="sec-protect-script">
(function() {{
  if (window.__educraftProtectionActive) return;
  window.__educraftProtectionActive = true;

  const WATERMARK_BASE = {wm_json};
  const ALLOW_FORM_INPUTS = {allow_inputs_js};
  const SESSION_TAG = Math.random().toString(36).slice(2, 7).toUpperCase();
  let toastTimer = null;
  let curtainHoldUntil = 0;
  let wmShiftStep = 0;

  // Блокируем Web API захвата экрана (getDisplayMedia)
  try {{
    if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {{
      navigator.mediaDevices.getDisplayMedia = function() {{
        showCurtain(2500);
        showProtectToast('Захват экрана и запись страницы запрещены системой защиты');
        return Promise.reject(new DOMException('Screen capture is disabled by content protection', 'NotAllowedError'));
      }};
    }}
  }} catch (e) {{}}

  function isEditableTarget(el) {{
    if (!ALLOW_FORM_INPUTS || !el) return false;
    const tag = (el.tagName || '').toUpperCase();
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
  }}

  function formatStamp() {{
    return WATERMARK_BASE + ' • ' + new Date().toLocaleString('ru-RU') + ' • #' + SESSION_TAG;
  }}

  function ensureProtectionNodes() {{
    if (!document.body) return;

    let wm = document.getElementById('sec-protect-watermark');
    if (!wm) {{
      wm = document.createElement('div');
      wm.id = 'sec-protect-watermark';
      wm.setAttribute('aria-hidden', 'true');
      const stamp = formatStamp();
      for (let i = 0; i < 21; i++) {{
        const span = document.createElement('span');
        span.textContent = stamp;
        wm.appendChild(span);
      }}
      document.body.appendChild(wm);
    }}

    if (!document.getElementById('sec-protect-curtain')) {{
      const curtain = document.createElement('div');
      curtain.id = 'sec-protect-curtain';
      curtain.innerHTML =
        '<div class="sec-shield-badge">Защита от скриншотов активна</div>' +
        '<div>Содержимое скрыто системой безопасности</div>' +
        '<small>Снятие скриншотов, копирование и сохранение материалов запрещены. Вернитесь в активное окно браузера для продолжения.</small>';
      document.body.appendChild(curtain);
    }}

    if (!document.getElementById('sec-protect-toast')) {{
      const toast = document.createElement('div');
      toast.id = 'sec-protect-toast';
      document.body.appendChild(toast);
    }}
  }}

  function refreshWatermark() {{
    const wm = document.getElementById('sec-protect-watermark');
    if (!wm) return;
    const stamp = formatStamp();
    wm.querySelectorAll('span').forEach(function(s) {{ s.textContent = stamp; }});
    wmShiftStep = (wmShiftStep + 1) % 4;
    const offsets = [[0, 0], [16, -12], [-14, 14], [10, 10]][wmShiftStep];
    wm.style.transform = 'translate(' + offsets[0] + 'px, ' + offsets[1] + 'px)';
  }}

  function showProtectToast(msg) {{
    ensureProtectionNodes();
    const toast = document.getElementById('sec-protect-toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function() {{ toast.classList.remove('visible'); }}, 2800);
  }}

  function showCurtain(tempMs) {{
    ensureProtectionNodes();
    if (document.body) document.body.classList.add('sec-screen-blocked');
    const curtain = document.getElementById('sec-protect-curtain');
    if (curtain) curtain.classList.add('active');
    if (tempMs && tempMs > 0) {{
      curtainHoldUntil = Math.max(curtainHoldUntil, Date.now() + tempMs);
      setTimeout(function() {{
        if (Date.now() >= curtainHoldUntil && !document.hidden && document.hasFocus()) {{
          hideCurtain();
        }}
      }}, tempMs + 40);
    }}
  }}

  function hideCurtain() {{
    if (Date.now() < curtainHoldUntil) return;
    if (document.body) document.body.classList.remove('sec-screen-blocked');
    const curtain = document.getElementById('sec-protect-curtain');
    if (curtain) curtain.classList.remove('active');
  }}

  function clearClipboardBestEffort() {{
    try {{
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText('Копирование и скриншоты защищённых материалов запрещены').catch(function() {{}});
      }}
    }} catch (e) {{}}
  }}

  // Блокировка печати через JS
  try {{
    window.print = function() {{
      showCurtain(2200);
      showProtectToast('Печать и сохранение материала запрещены системой защиты');
      return false;
    }};
  }} catch (e) {{}}

  window.addEventListener('beforeprint', function(e) {{
    showCurtain(3000);
    showProtectToast('Печать и сохранение материала запрещены системой защиты');
    if (e && e.preventDefault) e.preventDefault();
  }}, true);

  window.addEventListener('afterprint', function() {{
    if (!document.hidden && document.hasFocus()) hideCurtain();
  }}, true);

  // Блокировка контекстного меню, копирования, вырезания, перетаскивания и выделения
  ['contextmenu', 'copy', 'cut', 'dragstart'].forEach(function(evtName) {{
    document.addEventListener(evtName, function(e) {{
      e.preventDefault();
      e.stopPropagation();
      if (evtName === 'copy' || evtName === 'cut') {{
        showProtectToast('Копирование материалов запрещено системой защиты');
      }}
      return false;
    }}, true);
  }});

  document.addEventListener('selectstart', function(e) {{
    if (isEditableTarget(e.target)) return true;
    e.preventDefault();
    e.stopPropagation();
    return false;
  }}, true);

  // Блокировка горячих клавиш скриншотов, сохранения, печати, копирования и DevTools
  document.addEventListener('keydown', function(e) {{
    const key = (e.key || '').toLowerCase();
    const ctrl = e.ctrlKey || e.metaKey;
    const editable = isEditableTarget(e.target);

    // Скриншоты: PrintScreen, Alt/Ctrl/Shift+PrintScreen, Win+Shift+S, Cmd+Shift+3/4/5, Meta+Shift
    if (
      e.key === 'PrintScreen' ||
      e.code === 'PrintScreen' ||
      e.keyCode === 44 ||
      (e.metaKey && e.shiftKey) ||
      (e.ctrlKey && e.shiftKey && key === 's')
    ) {{
      e.preventDefault();
      e.stopPropagation();
      showCurtain(2600);
      clearClipboardBestEffort();
      showProtectToast('Снятие скриншотов запрещено системой защиты');
      return false;
    }}

    // Сохранение, печать, просмотр кода, DevTools
    if (
      e.key === 'F12' ||
      (ctrl && ['s', 'p', 'u'].includes(key)) ||
      (ctrl && e.shiftKey && ['i', 'j', 'c'].includes(key))
    ) {{
      e.preventDefault();
      e.stopPropagation();
      showProtectToast('Сохранение, печать и просмотр исходного кода запрещены');
      return false;
    }}

    // Копирование, вырезание, выделение всего
    if (ctrl && ['c', 'x', 'a'].includes(key) && !editable) {{
      e.preventDefault();
      e.stopPropagation();
      showProtectToast('Копирование материалов запрещено системой защиты');
      return false;
    }}
  }}, true);

  document.addEventListener('keyup', function(e) {{
    if (e.key === 'PrintScreen' || e.code === 'PrintScreen' || e.keyCode === 44) {{
      showCurtain(2600);
      clearClipboardBestEffort();
      showProtectToast('Снятие скриншотов запрещено системой защиты');
    }}
  }}, true);

  // Мгновенное скрытие содержимого при потере фокуса (Ножницы / Win+Shift+S / Lightshot / Alt+Tab / смена вкладки)
  window.addEventListener('blur', function() {{
    showCurtain(0);
  }}, true);

  window.addEventListener('focus', function() {{
    if (!document.hidden) hideCurtain();
  }}, true);

  document.addEventListener('visibilitychange', function() {{
    if (document.hidden) showCurtain(0);
    else if (document.hasFocus()) hideCurtain();
  }}, true);

  function initProtection() {{
    ensureProtectionNodes();
    if (document.hidden || !document.hasFocus()) {{
      showCurtain(0);
    }}

    // Периодическая проверка фокуса окна (перехватывает оверлеи ОС и программы захвата экрана)
    setInterval(function() {{
      if (document.hidden || !document.hasFocus()) {{
        showCurtain(0);
      }} else if (Date.now() >= curtainHoldUntil) {{
        hideCurtain();
      }}
    }}, 220);

    // Динамическое обновление времени и лёгкое смещение водяного знака
    setInterval(refreshWatermark, 20000);

    // Защита водяного знака и завесы от удаления или скрытия через DevTools
    const observer = new MutationObserver(function() {{
      const wm = document.getElementById('sec-protect-watermark');
      const curtain = document.getElementById('sec-protect-curtain');
      if (!wm || !curtain) {{
        ensureProtectionNodes();
      }} else if (wm.style.display === 'none' || wm.style.visibility === 'hidden' || wm.style.opacity === '0') {{
        wm.style.removeProperty('display');
        wm.style.removeProperty('visibility');
        wm.style.removeProperty('opacity');
      }}
    }});
    if (document.body) {{
      observer.observe(document.body, {{ childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class'] }});
    }}
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', initProtection);
  }} else {{
    initProtection();
  }}
}})();
</script>
"""


def inject_protection_into_html(html_text: str, protection_snippet: str) -> str:
    """Внедряет защитный слой перед закрывающим тегом </body> (или в конец документа)."""
    lower_html = html_text.lower()
    body_end = lower_html.rfind('</body>')
    if body_end != -1:
        return html_text[:body_end] + protection_snippet + html_text[body_end:]
    html_end = lower_html.rfind('</html>')
    if html_end != -1:
        return html_text[:html_end] + protection_snippet + html_text[html_end:]
    return html_text + protection_snippet


# =========================================================================
# МАРШРУТЫ СТРАНИЦ И API ВИТРИНЫ
# =========================================================================


# =========================================================================
# МОДУЛЬ ВИДЕОКОНФЕРЕНЦИЙ (ZOOM-АНАЛОГ НА 30+ УЧАСТНИКОВ + ЗАПИСЬ ЗВОНКОВ)
# =========================================================================

CONFERENCE_LOCK = threading.Lock()
CONFERENCE_ROOMS = {}  # { conf_id: { 'peers': {peer_id: {...}}, 'signals': {peer_id: [...]}, 'ended': False } }
PEER_TTL_SECONDS = 25


def _get_room_state_unlocked(conf_id: str) -> dict:
    room = CONFERENCE_ROOMS.get(conf_id)
    if room is None:
        room = {'peers': {}, 'signals': {}, 'ended': False}
        CONFERENCE_ROOMS[conf_id] = room
    now = time.time()
    stale = [pid for pid, p in room['peers'].items() if now - p.get('lastSeen', 0) > PEER_TTL_SECONDS]
    for pid in stale:
        room['peers'].pop(pid, None)
        room['signals'].pop(pid, None)
    return room


def get_conference_online_count(conf_id: str) -> int:
    with CONFERENCE_LOCK:
        room = _get_room_state_unlocked(conf_id)
        return len(room['peers'])


def has_conference_access(conn, user, conf_row) -> bool:
    """Проверяет доступ пользователя к видеоконференции и её записям."""
    if not user:
        return False
    if user['role'] == 'admin':
        return True
    course_id = (conf_row['course_id'] or '').strip()
    if not course_id:
        return True
    enrolled = conn.execute(
        'SELECT 1 FROM enrollments WHERE user_id = ? AND course_id = ?',
        (user['id'], course_id)
    ).fetchone()
    return enrolled is not None


def generate_recording_token(rec_id: str, user_id: str, ttl_seconds: int = 7200) -> str:
    exp = int(time.time()) + ttl_seconds
    uid = user_id or 'guest'
    payload = f"rec:{rec_id}:{uid}:{exp}"
    sig = hmac.new(
        app.secret_key.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:32]
    return f"{exp}.{sig}"


def verify_recording_token(token: str, rec_id: str, user_id: str) -> bool:
    if not token or '.' not in token:
        return False
    parts = token.split('.', 1)
    try:
        exp = int(parts[0])
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    uid = user_id or 'guest'
    payload = f"rec:{rec_id}:{uid}:{exp}"
    expected_sig = hmac.new(
        app.secret_key.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:32]
    return hmac.compare_digest(parts[1], expected_sig)


def serialize_conference(conn, row, user, include_admin_fields: bool = False) -> dict:
    rec_rows = conn.execute(
        'SELECT * FROM conference_recordings WHERE conference_id = ? ORDER BY rowid DESC',
        (row['id'],)
    ).fetchall()
    recordings = []
    uid = user['id'] if user else 'guest'
    for r in rec_rows:
        tok = generate_recording_token(r['id'], uid)
        recordings.append({
            'id': r['id'],
            'conferenceId': r['conference_id'],
            'title': r['title'],
            'fileSize': int(r['file_size'] or 0),
            'durationSec': int(r['duration_sec'] or 0),
            'recordedBy': r['recorded_by'] or '',
            'createdAt': r['created_at'] or '',
            'streamUrl': f"/api/conferences/recordings/{r['id']}/stream?token={tok}"
        })

    item = {
        'id': row['id'],
        'title': row['title'],
        'description': row['description'] or '',
        'courseId': row['course_id'] or '',
        'scheduledAt': row['scheduled_at'] or '',
        'maxParticipants': int(row['max_participants'] or 50),
        'engine': row['engine'] or 'builtin',
        'sfuDomain': row['sfu_domain'] or 'meet.ffmuc.net',
        'roomCode': row['room_code'] or row['id'],
        'hasPin': bool((row['access_pin'] or '').strip()),
        'allowRecording': bool(row['allow_recording']),
        'muteOnEntry': bool(row['mute_on_entry']),
        'status': row['status'] or 'scheduled',
        'onlineCount': get_conference_online_count(row['id']),
        'recordings': recordings,
        'createdAt': row['created_at'] or '',
    }
    if include_admin_fields:
        item['accessPin'] = row['access_pin'] or ''
    return item


def parse_design_json(raw_value) -> dict:
    """Безопасно объединяет сохранённые настройки дизайна страницы с параметрами по умолчанию."""
    merged = dict(DEFAULT_DESIGN)
    if not raw_value:
        return merged
    try:
        parsed = json.loads(raw_value) if isinstance(raw_value, str) else dict(raw_value)
        if isinstance(parsed, dict):
            for k in DEFAULT_DESIGN:
                if k in parsed and parsed[k] is not None:
                    merged[k] = parsed[k]
    except Exception:
        pass
    return merged


def serialize_page_photo(row) -> dict:
    return {
        'id': row['id'],
        'imageUrl': row['image_url'],
        'storedName': row['stored_name'],
        'title': row['title'],
        'caption': row['caption'],
        'pageTarget': row['page_target'],
        'targetEntityId': row['target_entity_id'],
        'placement': row['placement'],
        'align': row['align'],
        'widthPreset': row['width_preset'],
        'heightPx': int(row['height_px'] or 0),
        'objectFit': row['object_fit'] or 'cover',
        'rounded': row['rounded'] or 'xl',
        'layoutMode': row['layout_mode'] or 'card',
        'sortOrder': int(row['sort_order'] or 0),
        'isVisible': bool(row['is_visible']),
        'createdAt': row['created_at'] or '',
    }


@app.route('/uploads/images/<path:filename>', methods=['GET'])
def serve_uploaded_image(filename):
    """Безопасная отдача загруженных изображений (логотипы, обложки, фото-блоки страниц)."""
    safe_base = os.path.abspath(UPLOAD_IMAGE_DIR)
    target_path = os.path.abspath(os.path.join(UPLOAD_IMAGE_DIR, filename))
    if not target_path.startswith(safe_base + os.sep) or not os.path.isfile(target_path):
        abort(404)
    resp = send_file(target_path)
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@app.route('/')
def index():
    tpl_path = os.path.join(BASE_DIR, 'templates', 'index.html')
    if os.path.exists(tpl_path):
        return render_template('index.html')
    return send_file(os.path.join(BASE_DIR, 'index.html'))


@app.route('/api/state', methods=['GET'])
def api_get_state():
    conn = get_db()
    user = get_current_user(conn)

    s_row = conn.execute('SELECT * FROM settings WHERE id = 1').fetchone()
    settings = {
        'schoolName': s_row['school_name'],
        'heroTitle': s_row['hero_title'],
        'heroSubtitle': s_row['hero_subtitle'],
        'heroCtaText': s_row['hero_cta_text'],
        'accentColor': s_row['accent_color'],
        'contactEmail': s_row['contact_email'],
        'contactTelegram': s_row['contact_telegram'],
        'contactPhone': s_row['contact_phone'],
        'sbpQrImage': s_row['sbp_qr_image'] if 'sbp_qr_image' in s_row.keys() else '',
        'design': parse_design_json(s_row['design_json'] if 'design_json' in s_row.keys() else '{}'),
        'protection': {
            'watermark': bool(s_row['protect_watermark']),
            'blurOnUnfocus': bool(s_row['protect_blur']),
            'blockShortcutsAndCopy': bool(s_row['protect_shortcuts']),
        }
    }

    purchased_ids = []
    completed_ids = []
    if user:
        purchased_ids = [
            r['course_id'] for r in conn.execute(
                'SELECT course_id FROM enrollments WHERE user_id = ?', (user['id'],)
            ).fetchall()
        ]
        completed_ids = [
            r['lesson_id'] for r in conn.execute(
                'SELECT lesson_id FROM lesson_progress WHERE user_id = ?', (user['id'],)
            ).fetchall()
        ]
        user['purchasedCourseIds'] = purchased_ids
        user['completedLessonIds'] = completed_ids

    is_admin = bool(user and user['role'] == 'admin')
    courses_rows = conn.execute('SELECT * FROM courses').fetchall()
    courses = []
    for c in courses_rows:
        lessons_rows = conn.execute(
            'SELECT * FROM lessons WHERE course_id = ? ORDER BY sort_order ASC, rowid ASC',
            (c['id'],)
        ).fetchall()
        lessons_list = []
        for l in lessons_rows:
            has_video_file = bool(l['video_stored_name']) if 'video_stored_name' in l.keys() else False
            video_file_name = l['video_filename'] if 'video_filename' in l.keys() else ''
            has_video_url = bool((l['video_url'] or '').strip())
            item = {
                'id': l['id'],
                'sortOrder': l['sort_order'],
                'title': l['title'],
                'duration': l['duration'],
                'isFree': bool(l['is_free']),
                'contentType': l['content_type'],
                'hasPdf': bool(l['pdf_stored_name']),
                'pdfFileName': l['pdf_filename'],
                'hasHtml': bool(l['html_stored_name']),
                'htmlFileName': l['html_filename'],
                'hasVideo': has_video_file or has_video_url,
                'hasVideoFile': has_video_file,
                'videoFileName': video_file_name,
                'hasVideoUrl': has_video_url,
                'enableCodeTab': bool(l['enable_code_tab']) or l['content_type'] in ('code', 'all'),
                'unlocked': has_lesson_access(conn, user, l)
            }
            if is_admin:
                item['videoUrl'] = l['video_url']
                item['content'] = l['content']
                item['defaultHtml'] = l['default_html']
                item['defaultCss'] = l['default_css']
                item['defaultJs'] = l['default_js']
            lessons_list.append(item)
        courses.append({
            'id': c['id'],
            'title': c['title'],
            'category': c['category'],
            'price': c['price'],
            'coverGradient': c['cover_gradient'],
            'coverImage': c['cover_image'],
            'shortDescription': c['short_description'],
            'fullDescription': c['full_description'],
            'lessons': lessons_list
        })

    users_list = []
    if is_admin:
        all_users = conn.execute('SELECT id, name, email, role, created_at FROM users').fetchall()
        for u in all_users:
            u_courses = [
                r['course_id'] for r in conn.execute(
                    'SELECT course_id FROM enrollments WHERE user_id = ?', (u['id'],)
                ).fetchall()
            ]
            u_completed = [
                r['lesson_id'] for r in conn.execute(
                    'SELECT lesson_id FROM lesson_progress WHERE user_id = ?', (u['id'],)
                ).fetchall()
            ]
            users_list.append({
                'id': u['id'],
                'name': u['name'],
                'email': u['email'],
                'role': u['role'],
                'createdAt': u['created_at'],
                'purchasedCourseIds': u_courses,
                'completedLessonIds': u_completed
            })

    photo_rows = conn.execute(
        'SELECT * FROM page_photos ORDER BY sort_order ASC, rowid ASC'
    ).fetchall()
    page_photos = [serialize_page_photo(r) for r in photo_rows]

    conferences_list = []
    if user:
        conf_rows = conn.execute(
            "SELECT * FROM conferences ORDER BY CASE status WHEN 'live' THEN 0 WHEN 'scheduled' THEN 1 ELSE 2 END, rowid DESC"
        ).fetchall()
        for cr in conf_rows:
            if is_admin or has_conference_access(conn, user, cr):
                conferences_list.append(serialize_conference(conn, cr, user, include_admin_fields=is_admin))

    conn.close()
    return jsonify({
        'settings': settings,
        'courses': courses,
        'pagePhotos': page_photos,
        'conferences': conferences_list,
        'currentUser': user,
        'users': users_list
    })


# =========================================================================
# АВТОРИЗАЦИЯ И РЕГИСТРАЦИЯ
# =========================================================================

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE lower(email) = ?', (email,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Неверный email или пароль'}), 401

    session['user_id'] = user['id']
    return jsonify({'ok': True, 'userId': user['id']})


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not name or not email or len(password) < 3:
        return jsonify({'error': 'Заполните имя, email и пароль (минимум 3 символа)'}), 400

    conn = get_db()
    exists = conn.execute('SELECT 1 FROM users WHERE lower(email) = ?', (email,)).fetchone()
    if exists:
        conn.close()
        return jsonify({'error': 'Пользователь с таким email уже зарегистрирован'}), 409

    user_id = f'user-{uuid.uuid4().hex[:8]}'
    now_str = datetime.now().strftime('%Y-%m-%d')
    conn.execute(
        'INSERT INTO users (id, name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, name, email, generate_password_hash(password), 'student', now_str)
    )
    conn.commit()
    conn.close()

    session['user_id'] = user_id
    return jsonify({'ok': True, 'userId': user_id})


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.pop('user_id', None)
    return jsonify({'ok': True})


# =========================================================================
# ПОКУПКА КУРСА, ЗАЩИЩЁННЫЙ ПРОСМОТР УРОКА, PDF, HTML И ДОМАШНИЕ ЗАДАНИЯ
# =========================================================================

@app.route('/api/courses/<course_id>/buy', methods=['POST'])
@login_required
def api_buy_course(course_id):
    conn = get_db()
    course = conn.execute('SELECT id, title FROM courses WHERE id = ?', (course_id,)).fetchone()
    if not course:
        conn.close()
        return jsonify({'error': 'Курс не найден'}), 404

    now_str = datetime.now().strftime('%Y-%m-%d')
    conn.execute(
        'INSERT OR IGNORE INTO enrollments (user_id, course_id, purchased_at) VALUES (?, ?, ?)',
        (session['user_id'], course_id, now_str)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/lessons/<lesson_id>', methods=['GET'])
def api_get_lesson(lesson_id):
    conn = get_db()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not lesson:
        conn.close()
        return jsonify({'error': 'Урок не найден'}), 404

    user = get_current_user(conn)
    if not has_lesson_access(conn, user, lesson):
        conn.close()
        return jsonify({'error': 'Доступ закрыт. Приобретите курс для просмотра этого урока.'}), 403

    homework = None
    if user:
        hw = conn.execute(
            'SELECT answer_text, status, submitted_at FROM homework_submissions WHERE user_id = ? AND lesson_id = ?',
            (user['id'], lesson_id)
        ).fetchone()
        if hw:
            homework = dict(hw)

    has_video_file = bool(lesson['video_stored_name']) if 'video_stored_name' in lesson.keys() else False
    video_file_name = lesson['video_filename'] if 'video_filename' in lesson.keys() else ''
    video_url_val = (lesson['video_url'] or '').strip()
    video_stream_url = ''
    if has_video_file:
        v_token = generate_video_token(lesson['id'], user['id'] if user else 'guest')
        video_stream_url = f"/api/lessons/{lesson['id']}/video?token={v_token}"

    conn.close()
    return jsonify({
        'id': lesson['id'],
        'courseId': lesson['course_id'],
        'title': lesson['title'],
        'duration': lesson['duration'],
        'isFree': bool(lesson['is_free']),
        'videoUrl': video_url_val,
        'hasVideoUrl': bool(video_url_val),
        'hasVideoFile': has_video_file,
        'videoFileName': video_file_name,
        'videoStreamUrl': video_stream_url,
        'contentType': lesson['content_type'],
        'hasPdf': bool(lesson['pdf_stored_name']),
        'pdfFileName': lesson['pdf_filename'],
        'hasHtml': bool(lesson['html_stored_name']),
        'htmlFileName': lesson['html_filename'],
        'enableCodeTab': bool(lesson['enable_code_tab']) or lesson['content_type'] in ('code', 'all'),
        'content': lesson['content'],
        'defaultHtml': lesson['default_html'],
        'defaultCss': lesson['default_css'],
        'defaultJs': lesson['default_js'],
        'homework': homework
    })


@app.route('/view/lesson/<lesson_id>/pdf', methods=['GET'])
def view_protected_pdf_page(lesson_id):
    """Отдельная защищённая страница просмотра PDF (PDF.js на canvas + защита от копирования, скачивания и скриншотов)."""
    conn = get_db()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not lesson or not lesson['pdf_stored_name']:
        conn.close()
        abort(404)

    user = get_current_user(conn)
    if not has_lesson_access(conn, user, lesson):
        conn.close()
        abort(403)

    file_path = os.path.join(UPLOAD_PDF_DIR, lesson['pdf_stored_name'])
    conn.close()

    if not os.path.isfile(file_path):
        abort(404)

    wm_label = get_watermark_label(user)
    protection_snippet = build_page_protection_snippet(wm_label, is_pdf_viewer=True)
    pdf_title = lesson['pdf_filename'] or lesson['title'] or 'Методический материал'

    html_out = render_template(
        'pdf_viewer.html',
        pdf_title=pdf_title,
        pdf_api_url=f'/api/lessons/{lesson_id}/pdf',
        watermark_label=wm_label,
        protection_snippet=protection_snippet
    )
    resp = Response(html_out, mimetype='text/html; charset=utf-8')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


@app.route('/view/lesson/<lesson_id>/html', methods=['GET'])
def view_protected_html_page(lesson_id):
    """Отдельная защищённая страница интерактивного HTML-модуля с защитой от копирования, скачивания и скриншотов."""
    conn = get_db()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not lesson or not lesson['html_stored_name']:
        conn.close()
        abort(404)

    user = get_current_user(conn)
    if not has_lesson_access(conn, user, lesson):
        conn.close()
        abort(403)

    file_path = os.path.join(UPLOAD_HTML_DIR, lesson['html_stored_name'])
    conn.close()

    if not os.path.isfile(file_path):
        abort(404)

    with open(file_path, 'rb') as f:
        raw_bytes = f.read()

    try:
        html_text = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        html_text = raw_bytes.decode('cp1251', errors='replace')

    wm_label = get_watermark_label(user)
    protection_snippet = build_page_protection_snippet(wm_label, is_pdf_viewer=False)
    protected_html = inject_protection_into_html(html_text, protection_snippet)

    resp = Response(protected_html, mimetype='text/html; charset=utf-8')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


@app.route('/api/lessons/<lesson_id>/pdf', methods=['GET'])
def api_stream_protected_pdf(lesson_id):
    """Защищённая отдача байтов PDF только встроенному просмотрщику после проверки прав доступа."""
    if request.headers.get('X-Protected-Viewer') != '1':
        abort(403)

    conn = get_db()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not lesson or not lesson['pdf_stored_name']:
        conn.close()
        abort(404)

    user = get_current_user(conn)
    if not has_lesson_access(conn, user, lesson):
        conn.close()
        abort(403)

    file_path = os.path.join(UPLOAD_PDF_DIR, lesson['pdf_stored_name'])
    conn.close()

    if not os.path.isfile(file_path):
        abort(404)

    response = send_file(file_path, mimetype='application/pdf', as_attachment=False)
    response.headers['Content-Disposition'] = 'inline'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.route('/api/lessons/<lesson_id>/html', methods=['GET'])
def api_stream_protected_html(lesson_id):
    """Защищённая отдача HTML-файла урока только через защищённый просмотрщик."""
    if request.headers.get('X-Protected-Viewer') != '1':
        abort(403)

    conn = get_db()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not lesson or not lesson['html_stored_name']:
        conn.close()
        abort(404)

    user = get_current_user(conn)
    if not has_lesson_access(conn, user, lesson):
        conn.close()
        abort(403)

    file_path = os.path.join(UPLOAD_HTML_DIR, lesson['html_stored_name'])
    conn.close()

    if not os.path.isfile(file_path):
        abort(404)

    with open(file_path, 'rb') as f:
        raw_bytes = f.read()

    # Декодируем UTF-8 или Windows-1251, если файл сохранён в старой кодировке
    try:
        html_text = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        html_text = raw_bytes.decode('cp1251', errors='replace')

    wm_label = get_watermark_label(user)
    protection_snippet = build_page_protection_snippet(wm_label, is_pdf_viewer=False)
    protected_html = inject_protection_into_html(html_text, protection_snippet)

    resp = Response(protected_html, mimetype='text/html; charset=utf-8')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@app.route('/api/lessons/<lesson_id>/video-token', methods=['GET'])
def api_refresh_video_token(lesson_id):
    """Выдаёт свежий краткосрочный токен для защищённого стриминга видео."""
    if request.headers.get('X-Protected-Viewer') != '1':
        abort(403)

    conn = get_db()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not lesson or not lesson['video_stored_name']:
        conn.close()
        abort(404)

    user = get_current_user(conn)
    if not has_lesson_access(conn, user, lesson):
        conn.close()
        abort(403)
    conn.close()

    token = generate_video_token(lesson_id, user['id'] if user else 'guest')
    return jsonify({'videoStreamUrl': f'/api/lessons/{lesson_id}/video?token={token}'})


@app.route('/api/lessons/<lesson_id>/video', methods=['GET'])
def api_stream_protected_video(lesson_id):
    """Защищённый потоковый просмотр видеофайла урока (Range-чанки, токен, блокировка прямого скачивания)."""
    # Запрещаем прямое открытие ссылки в новой вкладке/документе (скачивание через браузер)
    fetch_dest = (request.headers.get('Sec-Fetch-Dest') or '').lower()
    if fetch_dest in ('document', 'iframe', 'object', 'embed'):
        abort(403)

    referer = request.headers.get('Referer', '')
    if referer:
        try:
            ref_host = urlparse(referer).netloc
            if ref_host and ref_host != request.host:
                abort(403)
        except Exception:
            abort(403)

    conn = get_db()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not lesson or not lesson['video_stored_name']:
        conn.close()
        abort(404)

    user = get_current_user(conn)
    if not has_lesson_access(conn, user, lesson):
        conn.close()
        abort(403)

    token = request.args.get('token', '')
    if not verify_video_token(token, lesson_id, user['id'] if user else 'guest'):
        conn.close()
        abort(403)

    file_path = os.path.join(UPLOAD_VIDEO_DIR, lesson['video_stored_name'])
    conn.close()

    if not os.path.isfile(file_path):
        abort(404)

    file_size = os.path.getsize(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith('video/'):
        mime_type = 'video/mp4'

    range_header = request.headers.get('Range')
    max_chunk = 2 * 1024 * 1024  # Максимум 2 МБ на один фрагмент потока

    if range_header:
        match = re.match(r'bytes=(\d*)-(\d*)', range_header.strip())
        if not match:
            abort(416)
        start_str, end_str = match.group(1), match.group(2)
        start = int(start_str) if start_str else 0
        if start >= file_size:
            abort(416)
        end = int(end_str) if end_str else min(start + max_chunk - 1, file_size - 1)
        end = min(end, start + max_chunk - 1, file_size - 1)
        length = end - start + 1

        with open(file_path, 'rb') as f:
            f.seek(start)
            data = f.read(length)

        resp = Response(data, status=206, mimetype=mime_type, direct_passthrough=True)
        resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(length)
    else:
        # Даже без Range отдаём начальный фрагмент с 206, чтобы исключить простое скачивание одним запросом
        end = min(max_chunk - 1, file_size - 1)
        length = end + 1
        with open(file_path, 'rb') as f:
            data = f.read(length)
        status_code = 206 if length < file_size else 200
        resp = Response(data, status=status_code, mimetype=mime_type, direct_passthrough=True)
        if status_code == 206:
            resp.headers['Content-Range'] = f'bytes 0-{end}/{file_size}'
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(length)

    resp.headers['Content-Disposition'] = 'inline'
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


@app.route('/api/lessons/<lesson_id>/complete', methods=['POST'])
@login_required
def api_toggle_lesson_complete(lesson_id):
    conn = get_db()
    user_id = session['user_id']
    exists = conn.execute(
        'SELECT 1 FROM lesson_progress WHERE user_id = ? AND lesson_id = ?',
        (user_id, lesson_id)
    ).fetchone()
    if exists:
        conn.execute('DELETE FROM lesson_progress WHERE user_id = ? AND lesson_id = ?', (user_id, lesson_id))
        completed = False
    else:
        conn.execute(
            'INSERT INTO lesson_progress (user_id, lesson_id, completed_at) VALUES (?, ?, ?)',
            (user_id, lesson_id, datetime.now().strftime('%Y-%m-%d %H:%M'))
        )
        completed = True
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'completed': completed})


@app.route('/api/lessons/<lesson_id>/homework', methods=['POST'])
@login_required
def api_submit_homework(lesson_id):
    data = request.get_json(silent=True) or {}
    answer_text = (data.get('answerText') or '').strip()
    if not answer_text:
        return jsonify({'error': 'Введите текст ответа на домашнее задание'}), 400

    conn = get_db()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    hw_id = f'hw-{uuid.uuid4().hex[:8]}'
    conn.execute("""
        INSERT INTO homework_submissions (id, user_id, lesson_id, answer_text, status, submitted_at)
        VALUES (?, ?, ?, ?, 'submitted', ?)
        ON CONFLICT(user_id, lesson_id) DO UPDATE SET
            answer_text = excluded.answer_text,
            status = 'submitted',
            submitted_at = excluded.submitted_at
    """, (hw_id, session['user_id'], lesson_id, answer_text, now_str))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'submittedAt': now_str})


# =========================================================================
# API КОНСТРУКТОРА САЙТА (ТОЛЬКО ДЛЯ АДМИНИСТРАТОРА)
# =========================================================================

@app.route('/api/admin/settings', methods=['PUT'])
@admin_required
def api_admin_update_settings():
    data = request.get_json(silent=True) or {}
    protection = data.get('protection') or {}
    conn = get_db()
    conn.execute("""
        UPDATE settings SET
            school_name = ?,
            hero_title = ?,
            hero_subtitle = ?,
            hero_cta_text = ?,
            accent_color = ?,
            contact_email = ?,
            contact_telegram = ?,
            contact_phone = ?,
            protect_watermark = ?,
            protect_blur = ?,
            protect_shortcuts = ?,
            sbp_qr_image = ?
        WHERE id = 1
    """, (
        data.get('schoolName', 'Моя Онлайн-Школа'),
        data.get('heroTitle', ''),
        data.get('heroSubtitle', ''),
        data.get('heroCtaText', 'Выбрать курс'),
        data.get('accentColor', 'indigo'),
        data.get('contactEmail', ''),
        data.get('contactTelegram', ''),
        data.get('contactPhone', ''),
        1 if protection.get('watermark', True) else 0,
        1 if protection.get('blurOnUnfocus', True) else 0,
        1 if protection.get('blockShortcutsAndCopy', True) else 0,
        data.get('sbpQrImage', ''),
    ))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/admin/design', methods=['PUT'])
@admin_required
def api_admin_update_design():
    """Сохраняет параметры дизайна страниц (шрифт, цвета, сетка, скругления, логотип, Hero)."""
    data = request.get_json(silent=True) or {}
    clean_design = parse_design_json(data)
    # Ограничиваем числовые поля безопасными диапазонами
    try:
        cols_val = int(clean_design.get('catalogColumns', 3))
        clean_design['catalogColumns'] = cols_val if cols_val in (2, 3, 4) else 3
    except (TypeError, ValueError):
        clean_design['catalogColumns'] = 3
    try:
        lh = int(clean_design.get('logoHeight', 36))
        clean_design['logoHeight'] = max(24, min(72, lh))
    except (TypeError, ValueError):
        clean_design['logoHeight'] = 36

    conn = get_db()
    conn.execute(
        'UPDATE settings SET design_json = ? WHERE id = 1',
        (json.dumps(clean_design, ensure_ascii=False),)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'design': clean_design})


@app.route('/api/admin/images/upload', methods=['POST'])
@admin_required
def api_admin_upload_image():
    """Загружает изображение на сервер для логотипа, обложки курса или фото-блока."""
    file = request.files.get('image') or request.files.get('photo') or request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': 'Файл изображения не передан'}), 400
    orig_name = file.filename.strip()
    _, ext = os.path.splitext(orig_name.lower())
    if ext not in ALLOWED_IMAGE_EXTS:
        return jsonify({'error': 'Поддерживаются изображения: JPG, PNG, WebP, GIF, SVG'}), 400

    stored_name = f'img_{uuid.uuid4().hex[:12]}{ext}'
    save_path = os.path.join(UPLOAD_IMAGE_DIR, stored_name)
    file.save(save_path)
    return jsonify({
        'ok': True,
        'url': f'/uploads/images/{stored_name}',
        'storedName': stored_name,
        'fileName': orig_name
    })


@app.route('/api/admin/photos', methods=['POST'])
@admin_required
def api_admin_create_photo():
    """Добавляет новое фото с заданным местом расположения на страницах сайта."""
    stored_name = ''
    if request.content_type and 'multipart/form-data' in request.content_type:
        form = request.form
        image_url = (form.get('imageUrl') or '').strip()
        file = request.files.get('photo') or request.files.get('image')
        if file and file.filename:
            orig_name = file.filename.strip()
            _, ext = os.path.splitext(orig_name.lower())
            if ext not in ALLOWED_IMAGE_EXTS:
                return jsonify({'error': 'Поддерживаются изображения: JPG, PNG, WebP, GIF, SVG'}), 400
            stored_name = f'photo_{uuid.uuid4().hex[:12]}{ext}'
            file.save(os.path.join(UPLOAD_IMAGE_DIR, stored_name))
            image_url = f'/uploads/images/{stored_name}'
        data = dict(form)
    else:
        data = request.get_json(silent=True) or {}
        image_url = (data.get('imageUrl') or '').strip()
        stored_name = (data.get('storedName') or '').strip()

    if not image_url:
        return jsonify({'error': 'Загрузите файл изображения или укажите ссылку на фото'}), 400

    photo_id = f'photo-{uuid.uuid4().hex[:8]}'
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    try:
        height_px = max(0, min(900, int(data.get('heightPx') or 0)))
    except (TypeError, ValueError):
        height_px = 0
    is_visible = 0 if str(data.get('isVisible', '1')).lower() in ('0', 'false', 'no') else 1

    conn = get_db()
    max_order = conn.execute('SELECT COALESCE(MAX(sort_order), 0) AS m FROM page_photos').fetchone()['m']
    conn.execute("""
        INSERT INTO page_photos (
            id, image_url, stored_name, title, caption,
            page_target, target_entity_id, placement, align,
            width_preset, height_px, object_fit, rounded, layout_mode,
            sort_order, is_visible, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        photo_id,
        image_url,
        stored_name,
        (data.get('title') or '').strip(),
        (data.get('caption') or '').strip(),
        (data.get('pageTarget') or 'catalog').strip(),
        (data.get('targetEntityId') or '').strip(),
        (data.get('placement') or 'after_hero').strip(),
        (data.get('align') or 'center').strip(),
        (data.get('widthPreset') or 'medium').strip(),
        height_px,
        (data.get('objectFit') or 'cover').strip(),
        (data.get('rounded') or 'xl').strip(),
        (data.get('layoutMode') or 'card').strip(),
        max_order + 1,
        is_visible,
        now_str
    ))
    conn.commit()
    row = conn.execute('SELECT * FROM page_photos WHERE id = ?', (photo_id,)).fetchone()
    conn.close()
    return jsonify({'ok': True, 'photo': serialize_page_photo(row)})


@app.route('/api/admin/photos/reorder', methods=['PUT', 'POST'])
@admin_required
def api_admin_reorder_photos():
    """Изменяет порядок отображения фото-блоков."""
    data = request.get_json(silent=True) or {}
    photo_ids = data.get('photoIds')
    if not isinstance(photo_ids, list) or not photo_ids:
        return jsonify({'error': 'Передайте корректный список ID фото'}), 400

    conn = get_db()
    existing_ids = [
        r['id'] for r in conn.execute('SELECT id FROM page_photos ORDER BY sort_order ASC, rowid ASC').fetchall()
    ]
    existing_set = set(existing_ids)
    ordered = [pid for pid in photo_ids if pid in existing_set]
    for pid in existing_ids:
        if pid not in ordered:
            ordered.append(pid)
    for idx, pid in enumerate(ordered, start=1):
        conn.execute('UPDATE page_photos SET sort_order = ? WHERE id = ?', (idx, pid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'photoIds': ordered})


@app.route('/api/admin/photos/<photo_id>', methods=['PUT', 'DELETE'])
@admin_required
def api_admin_manage_photo(photo_id):
    """Обновляет параметры расположения/оформления фото или удаляет его."""
    conn = get_db()
    existing = conn.execute('SELECT * FROM page_photos WHERE id = ?', (photo_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({'error': 'Фото не найдено'}), 404

    if request.method == 'DELETE':
        stored = existing['stored_name']
        conn.execute('DELETE FROM page_photos WHERE id = ?', (photo_id,))
        conn.commit()
        if stored:
            still_used = conn.execute(
                'SELECT 1 FROM page_photos WHERE stored_name = ?', (stored,)
            ).fetchone()
            if not still_used:
                p = os.path.join(UPLOAD_IMAGE_DIR, stored)
                if os.path.isfile(p):
                    os.remove(p)
        conn.close()
        return jsonify({'ok': True})

    data = request.get_json(silent=True) or {}
    try:
        height_px = max(0, min(900, int(data.get('heightPx', existing['height_px']) or 0)))
    except (TypeError, ValueError):
        height_px = int(existing['height_px'] or 0)

    is_visible = existing['is_visible']
    if 'isVisible' in data:
        is_visible = 1 if data['isVisible'] else 0

    conn.execute("""
        UPDATE page_photos SET
            image_url = ?,
            stored_name = ?,
            title = ?,
            caption = ?,
            page_target = ?,
            target_entity_id = ?,
            placement = ?,
            align = ?,
            width_preset = ?,
            height_px = ?,
            object_fit = ?,
            rounded = ?,
            layout_mode = ?,
            is_visible = ?
        WHERE id = ?
    """, (
        (data.get('imageUrl', existing['image_url']) or '').strip(),
        (data.get('storedName', existing['stored_name']) or '').strip(),
        (data.get('title', existing['title']) or '').strip(),
        (data.get('caption', existing['caption']) or '').strip(),
        (data.get('pageTarget', existing['page_target']) or 'catalog').strip(),
        (data.get('targetEntityId', existing['target_entity_id']) or '').strip(),
        (data.get('placement', existing['placement']) or 'after_hero').strip(),
        (data.get('align', existing['align']) or 'center').strip(),
        (data.get('widthPreset', existing['width_preset']) or 'medium').strip(),
        height_px,
        (data.get('objectFit', existing['object_fit']) or 'cover').strip(),
        (data.get('rounded', existing['rounded']) or 'xl').strip(),
        (data.get('layoutMode', existing['layout_mode']) or 'card').strip(),
        is_visible,
        photo_id
    ))
    conn.commit()
    row = conn.execute('SELECT * FROM page_photos WHERE id = ?', (photo_id,)).fetchone()
    conn.close()
    return jsonify({'ok': True, 'photo': serialize_page_photo(row)})


@app.route('/api/admin/courses', methods=['POST'])
@admin_required
def api_admin_create_course():
    data = request.get_json(silent=True) or {}
    course_id = f'course-{uuid.uuid4().hex[:8]}'
    conn = get_db()
    conn.execute(
        'INSERT INTO courses VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (
            course_id,
            data.get('title', 'Новый онлайн-курс'),
            data.get('category', 'Общее'),
            int(data.get('price', 4900)),
            data.get('coverGradient', 'grad-indigo'),
            data.get('coverImage', ''),
            data.get('shortDescription', 'Краткое описание программы обучения'),
            data.get('fullDescription', 'Подробная программа курса и результаты после прохождения.')
        )
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'courseId': course_id})


@app.route('/api/admin/courses/<course_id>', methods=['PUT', 'DELETE'])
@admin_required
def api_admin_manage_course(course_id):
    conn = get_db()
    if request.method == 'DELETE':
        conn.execute('DELETE FROM courses WHERE id = ?', (course_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    data = request.get_json(silent=True) or {}
    conn.execute("""
        UPDATE courses SET
            title = ?, category = ?, price = ?, cover_gradient = ?,
            cover_image = ?, short_description = ?, full_description = ?
        WHERE id = ?
    """, (
        data.get('title', ''),
        data.get('category', ''),
        int(data.get('price', 0)),
        data.get('coverGradient', 'grad-indigo'),
        data.get('coverImage', ''),
        data.get('shortDescription', ''),
        data.get('fullDescription', ''),
        course_id
    ))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/admin/courses/<course_id>/lessons', methods=['POST'])
@admin_required
def api_admin_create_lesson(course_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    max_order = conn.execute(
        'SELECT COALESCE(MAX(sort_order), 0) AS m FROM lessons WHERE course_id = ?',
        (course_id,)
    ).fetchone()['m']
    lesson_id = f'lesson-{uuid.uuid4().hex[:8]}'
    conn.execute(
        """INSERT INTO lessons (
                id, course_id, sort_order, title, duration, is_free, video_url,
                content_type, pdf_filename, pdf_stored_name, html_filename, html_stored_name,
                enable_code_tab, content, default_html, default_css, default_js
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            lesson_id,
            course_id,
            max_order + 1,
            data.get('title', 'Новый урок'),
            data.get('duration', '25 мин'),
            1 if data.get('isFree') else 0,
            data.get('videoUrl', ''),
            data.get('contentType', 'text'),
            '', '', '', '',
            1 if data.get('enableCodeTab') else 0,
            data.get('content', 'Текст конспекта нового урока...'),
            data.get('defaultHtml', '<h1>Практическое задание</h1>'),
            data.get('defaultCss', 'body { font-family: sans-serif; padding: 20px; }'),
            data.get('defaultJs', 'console.log("Урок запущен");')
        )
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'lessonId': lesson_id})


@app.route('/api/admin/courses/<course_id>/lessons/reorder', methods=['PUT', 'POST'])
@admin_required
def api_admin_reorder_lessons(course_id):
    """Изменяет порядок уроков внутри курса."""
    data = request.get_json(silent=True) or {}
    lesson_ids = data.get('lessonIds')
    if not isinstance(lesson_ids, list) or not lesson_ids:
        return jsonify({'error': 'Передайте корректный список ID уроков'}), 400

    conn = get_db()
    existing_rows = conn.execute(
        'SELECT id FROM lessons WHERE course_id = ? ORDER BY sort_order ASC, rowid ASC',
        (course_id,)
    ).fetchall()
    existing_ids = [r['id'] for r in existing_rows]
    existing_set = set(existing_ids)

    ordered = [lid for lid in lesson_ids if lid in existing_set]
    for lid in existing_ids:
        if lid not in ordered:
            ordered.append(lid)

    for idx, lid in enumerate(ordered, start=1):
        conn.execute(
            'UPDATE lessons SET sort_order = ? WHERE id = ? AND course_id = ?',
            (idx, lid, course_id)
        )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'lessonIds': ordered})


@app.route('/api/admin/lessons/<lesson_id>', methods=['PUT', 'DELETE'])
@admin_required
def api_admin_manage_lesson(lesson_id):
    conn = get_db()
    existing = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({'error': 'Урок не найден'}), 404

    if request.method == 'DELETE':
        if existing['pdf_stored_name'] and existing['pdf_stored_name'] != 'demo_typography.pdf':
            p = os.path.join(UPLOAD_PDF_DIR, existing['pdf_stored_name'])
            if os.path.exists(p):
                os.remove(p)
        if existing['html_stored_name']:
            h = os.path.join(UPLOAD_HTML_DIR, existing['html_stored_name'])
            if os.path.exists(h):
                os.remove(h)
        if 'video_stored_name' in existing.keys() and existing['video_stored_name']:
            v = os.path.join(UPLOAD_VIDEO_DIR, existing['video_stored_name'])
            if os.path.exists(v):
                os.remove(v)
        conn.execute('DELETE FROM lessons WHERE id = ?', (lesson_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    data = request.get_json(silent=True) or {}
    default_html = data['defaultHtml'] if 'defaultHtml' in data else existing['default_html']
    default_css = data['defaultCss'] if 'defaultCss' in data else existing['default_css']
    default_js = data['defaultJs'] if 'defaultJs' in data else existing['default_js']

    conn.execute("""
        UPDATE lessons SET
            title = ?, duration = ?, is_free = ?, video_url = ?,
            content_type = ?, enable_code_tab = ?, content = ?,
            default_html = ?, default_css = ?, default_js = ?
        WHERE id = ?
    """, (
        data.get('title', existing['title']),
        data.get('duration', existing['duration']),
        1 if data.get('isFree', existing['is_free']) else 0,
        data.get('videoUrl', existing['video_url']),
        data.get('contentType', existing['content_type']),
        1 if data.get('enableCodeTab', existing['enable_code_tab']) else 0,
        data.get('content', existing['content']),
        default_html,
        default_css,
        default_js,
        lesson_id
    ))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/admin/lessons/<lesson_id>/pdf', methods=['POST', 'DELETE'])
@admin_required
def api_admin_upload_lesson_pdf(lesson_id):
    """Загрузка или удаление PDF-файла методички на Python-сервере."""
    conn = get_db()
    old = conn.execute('SELECT pdf_stored_name FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not old:
        conn.close()
        return jsonify({'error': 'Урок не найден'}), 404

    if request.method == 'DELETE':
        if old['pdf_stored_name'] and old['pdf_stored_name'] != 'demo_typography.pdf':
            old_path = os.path.join(UPLOAD_PDF_DIR, old['pdf_stored_name'])
            if os.path.exists(old_path):
                os.remove(old_path)
        conn.execute(
            "UPDATE lessons SET pdf_filename = '', pdf_stored_name = '' WHERE id = ?",
            (lesson_id,)
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    if 'pdf' not in request.files:
        conn.close()
        return jsonify({'error': 'Файл PDF не передан'}), 400
    file = request.files['pdf']
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        conn.close()
        return jsonify({'error': 'Разрешена загрузка только файлов в формате .pdf'}), 400

    stored_name = f'{lesson_id}_{uuid.uuid4().hex[:8]}.pdf'
    save_path = os.path.join(UPLOAD_PDF_DIR, stored_name)
    file.save(save_path)

    if old['pdf_stored_name'] and old['pdf_stored_name'] != 'demo_typography.pdf':
        old_path = os.path.join(UPLOAD_PDF_DIR, old['pdf_stored_name'])
        if os.path.exists(old_path):
            os.remove(old_path)

    conn.execute(
        'UPDATE lessons SET pdf_filename = ?, pdf_stored_name = ?, content_type = ? WHERE id = ?',
        (file.filename, stored_name, 'pdf', lesson_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'pdfFileName': file.filename})


@app.route('/api/admin/lessons/<lesson_id>/html', methods=['POST', 'DELETE'])
@admin_required
def api_admin_upload_lesson_html(lesson_id):
    """Загрузка или удаление интерактивного HTML-файла урока на Python-сервере."""
    conn = get_db()
    old = conn.execute('SELECT html_stored_name FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not old:
        conn.close()
        return jsonify({'error': 'Урок не найден'}), 404

    if request.method == 'DELETE':
        if old['html_stored_name']:
            old_path = os.path.join(UPLOAD_HTML_DIR, old['html_stored_name'])
            if os.path.exists(old_path):
                os.remove(old_path)
        conn.execute(
            "UPDATE lessons SET html_filename = '', html_stored_name = '' WHERE id = ?",
            (lesson_id,)
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    if 'html' not in request.files:
        conn.close()
        return jsonify({'error': 'HTML-файл не передан'}), 400
    file = request.files['html']
    fname_lower = (file.filename or '').lower()
    if not fname_lower or not (fname_lower.endswith('.html') or fname_lower.endswith('.htm')):
        conn.close()
        return jsonify({'error': 'Разрешена загрузка только файлов в формате .html или .htm'}), 400

    stored_name = f'{lesson_id}_{uuid.uuid4().hex[:8]}.html'
    save_path = os.path.join(UPLOAD_HTML_DIR, stored_name)
    file.save(save_path)

    with open(save_path, 'rb') as f:
        raw_bytes = f.read()
    try:
        decoded_html = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        decoded_html = raw_bytes.decode('cp1251', errors='replace')

    if old['html_stored_name']:
        old_path = os.path.join(UPLOAD_HTML_DIR, old['html_stored_name'])
        if os.path.exists(old_path):
            os.remove(old_path)

    conn.execute(
        """UPDATE lessons
           SET html_filename = ?, html_stored_name = ?, content_type = ?, default_html = ?
           WHERE id = ?""",
        (file.filename, stored_name, 'html', decoded_html, lesson_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'htmlFileName': file.filename})


@app.route('/api/admin/lessons/<lesson_id>/video', methods=['POST', 'DELETE'])
@admin_required
def api_admin_upload_lesson_video(lesson_id):
    """Загрузка или удаление видеофайла урока на Python-сервере."""
    conn = get_db()
    old = conn.execute('SELECT video_stored_name, content_type FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not old:
        conn.close()
        return jsonify({'error': 'Урок не найден'}), 404

    if request.method == 'DELETE':
        if old['video_stored_name']:
            old_path = os.path.join(UPLOAD_VIDEO_DIR, old['video_stored_name'])
            if os.path.exists(old_path):
                os.remove(old_path)
        conn.execute(
            "UPDATE lessons SET video_filename = '', video_stored_name = '' WHERE id = ?",
            (lesson_id,)
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    if 'video' not in request.files:
        conn.close()
        return jsonify({'error': 'Видеофайл не передан'}), 400
    file = request.files['video']
    orig_name = (file.filename or '').strip()
    _, ext = os.path.splitext(orig_name.lower())
    if not orig_name or ext not in ALLOWED_VIDEO_EXTS:
        conn.close()
        return jsonify({'error': 'Поддерживаются видеофайлы форматов: .mp4, .webm, .mov, .m4v, .ogg'}), 400

    stored_name = f'{lesson_id}_{uuid.uuid4().hex[:8]}{ext}'
    save_path = os.path.join(UPLOAD_VIDEO_DIR, stored_name)
    file.save(save_path)

    if old['video_stored_name']:
        old_path = os.path.join(UPLOAD_VIDEO_DIR, old['video_stored_name'])
        if os.path.exists(old_path):
            os.remove(old_path)

    next_type = 'video' if old['content_type'] == 'text' else old['content_type']
    conn.execute(
        'UPDATE lessons SET video_filename = ?, video_stored_name = ?, content_type = ? WHERE id = ?',
        (orig_name, stored_name, next_type, lesson_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'videoFileName': orig_name})


@app.route('/api/admin/users', methods=['POST'])
@admin_required
def api_admin_create_user():
    """Ручное добавление ученика или администратора из конструктора."""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = (data.get('role') or 'student').strip().lower()
    course_ids = data.get('courseIds') or []

    if not name or not email or not password:
        return jsonify({'error': 'Заполните имя, email и пароль пользователя'}), 400
    if len(password) < 3:
        return jsonify({'error': 'Пароль должен содержать минимум 3 символа'}), 400
    if role not in ('student', 'admin'):
        return jsonify({'error': 'Некорректная роль. Допустимо: student или admin'}), 400

    conn = get_db()
    exists = conn.execute('SELECT 1 FROM users WHERE lower(email) = ?', (email,)).fetchone()
    if exists:
        conn.close()
        return jsonify({'error': 'Пользователь с таким email уже существует'}), 409

    user_id = f'user-{uuid.uuid4().hex[:8]}'
    now_str = datetime.now().strftime('%Y-%m-%d')
    conn.execute(
        'INSERT INTO users (id, name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, name, email, generate_password_hash(password), role, now_str)
    )

    if isinstance(course_ids, list) and course_ids:
        valid_courses = {
            r['id'] for r in conn.execute('SELECT id FROM courses').fetchall()
        }
        for cid in course_ids:
            if cid in valid_courses:
                conn.execute(
                    'INSERT OR IGNORE INTO enrollments (user_id, course_id, purchased_at) VALUES (?, ?, ?)',
                    (user_id, cid, now_str)
                )

    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'userId': user_id})


@app.route('/api/admin/users/<user_id>/role', methods=['PUT'])
@admin_required
def api_admin_update_user_role(user_id):
    """Изменение роли пользователя (Ученик / Администратор)."""
    data = request.get_json(silent=True) or {}
    new_role = (data.get('role') or '').strip().lower()
    if new_role not in ('student', 'admin'):
        return jsonify({'error': 'Некорректная роль. Допустимо: student или admin'}), 400

    conn = get_db()
    target = conn.execute('SELECT id, role FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target:
        conn.close()
        return jsonify({'error': 'Пользователь не найден'}), 404

    if target['id'] == session.get('user_id') and new_role != 'admin':
        conn.close()
        return jsonify({'error': 'Нельзя снять права администратора с текущего аккаунта'}), 400

    if target['role'] == 'admin' and new_role != 'admin':
        admin_cnt = conn.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin'").fetchone()['cnt']
        if admin_cnt <= 1:
            conn.close()
            return jsonify({'error': 'В системе должен остаться хотя бы один администратор'}), 400

    conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'role': new_role})


@app.route('/api/admin/users/<user_id>', methods=['PUT', 'DELETE'])
@admin_required
def api_admin_manage_user(user_id):
    """Редактирование данных пользователя (Имя и фамилия, Email, Пароль, Роль) или удаление."""
    conn = get_db()
    target = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target:
        conn.close()
        return jsonify({'error': 'Пользователь не найден'}), 404

    if request.method == 'DELETE':
        if user_id == session.get('user_id'):
            conn.close()
            return jsonify({'error': 'Нельзя удалить текущий аккаунт администратора'}), 400
        if target['role'] == 'admin':
            admin_cnt = conn.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin'").fetchone()['cnt']
            if admin_cnt <= 1:
                conn.close()
                return jsonify({'error': 'Нельзя удалить единственного администратора'}), 400
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    # PUT: редактирование Имени и фамилии, Email, Пароля и Роли
    data = request.get_json(silent=True) or {}
    name = (data.get('name') if 'name' in data else target['name'] or '').strip()
    email = (data.get('email') if 'email' in data else target['email'] or '').strip().lower()
    password = data.get('password') or ''
    role = (data.get('role') if 'role' in data else target['role'] or 'student').strip().lower()

    if not name or not email:
        conn.close()
        return jsonify({'error': 'Имя и фамилия, а также Email не могут быть пустыми'}), 400
    if '@' not in email or '.' not in email.split('@')[-1]:
        conn.close()
        return jsonify({'error': 'Укажите корректный Email адрес'}), 400
    if password and len(password) < 3:
        conn.close()
        return jsonify({'error': 'Новый пароль должен содержать минимум 3 символа'}), 400
    if role not in ('student', 'admin'):
        conn.close()
        return jsonify({'error': 'Некорректная роль. Допустимо: student или admin'}), 400

    email_taken = conn.execute(
        'SELECT 1 FROM users WHERE lower(email) = ? AND id != ?',
        (email, user_id)
    ).fetchone()
    if email_taken:
        conn.close()
        return jsonify({'error': 'Этот Email уже используется другим пользователем'}), 409

    if target['id'] == session.get('user_id') and role != 'admin':
        conn.close()
        return jsonify({'error': 'Нельзя снять права администратора с текущего аккаунта'}), 400

    if target['role'] == 'admin' and role != 'admin':
        admin_cnt = conn.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin'").fetchone()['cnt']
        if admin_cnt <= 1:
            conn.close()
            return jsonify({'error': 'В системе должен остаться хотя бы один администратор'}), 400

    if password:
        conn.execute(
            'UPDATE users SET name = ?, email = ?, password_hash = ?, role = ? WHERE id = ?',
            (name, email, generate_password_hash(password), role, user_id)
        )
    else:
        conn.execute(
            'UPDATE users SET name = ?, email = ?, role = ? WHERE id = ?',
            (name, email, role, user_id)
        )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'user': {'id': user_id, 'name': name, 'email': email, 'role': role}})


@app.route('/api/admin/users/<user_id>/courses/<course_id>', methods=['POST', 'DELETE'])
@admin_required
def api_admin_user_access(user_id, course_id):
    conn = get_db()
    if request.method == 'POST':
        conn.execute(
            'INSERT OR IGNORE INTO enrollments (user_id, course_id, purchased_at) VALUES (?, ?, ?)',
            (user_id, course_id, datetime.now().strftime('%Y-%m-%d'))
        )
    else:
        conn.execute(
            'DELETE FROM enrollments WHERE user_id = ? AND course_id = ?',
            (user_id, course_id)
        )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})



# =========================================================================
# МАРШРУТЫ ВИДЕОКОНФЕРЕНЦИЙ (ZOOM-МОДУЛЬ 30+ УЧАСТНИКОВ + ЗАПИСЬ ЗВОНКОВ)
# =========================================================================

@app.route('/conference/<conf_id>', methods=['GET'])
def view_conference_room(conf_id):
    """Отдельная полноэкранная страница видеоконференции (Zoom-интерфейс)."""
    conn = get_db()
    user = get_current_user(conn)
    if not user:
        conn.close()
        return Response(
            """<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Вход в конференцию</title>
            <style>body{font-family:Inter,sans-serif;background:#0f172a;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:24px;text-align:center;}
            .box{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:32px;max-width:420px;}
            a{display:inline-block;margin-top:16px;padding:10px 20px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:10px;font-weight:700;}</style></head>
            <body><div class="box"><h2>Требуется авторизация</h2><p>Войдите в свой аккаунт на главной странице школы, чтобы подключиться к видеоконференции.</p>
            <a href="/">Перейти на главную</a></div></body></html>""",
            status=401, mimetype='text/html; charset=utf-8'
        )

    conf = conn.execute('SELECT * FROM conferences WHERE id = ?', (conf_id,)).fetchone()
    if not conf:
        conn.close()
        abort(404)

    if not has_conference_access(conn, user, conf):
        conn.close()
        return Response(
            """<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Доступ ограничен</title>
            <style>body{font-family:Inter,sans-serif;background:#0f172a;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:24px;text-align:center;}
            .box{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:32px;max-width:440px;}
            a{display:inline-block;margin-top:16px;padding:10px 20px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:10px;font-weight:700;}</style></head>
            <body><div class="box"><h2>Доступ к видеоконференции закрыт</h2><p>Эта конференция предназначена для участников соответствующего курса.</p>
            <a href="/">Вернуться в каталог</a></div></body></html>""",
            status=403, mimetype='text/html; charset=utf-8'
        )

    s_row = conn.execute('SELECT school_name FROM settings WHERE id = 1').fetchone()
    school_name = s_row['school_name'] if s_row else 'Онлайн-школа'
    conf_data = serialize_conference(conn, conf, user, include_admin_fields=(user['role'] == 'admin'))
    conn.close()

    resp = Response(
        render_template(
            'conference.html',
            school_name=school_name,
            conf=conf_data,
            user=user,
            is_host=(user['role'] == 'admin')
        ),
        mimetype='text/html; charset=utf-8'
    )
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


@app.route('/api/admin/conferences', methods=['POST'])
@admin_required
def api_admin_create_conference():
    """Создание новой видеоконференции в конструкторе."""
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'Укажите название видеоконференции'}), 400

    conf_id = f'conf-{uuid.uuid4().hex[:8]}'
    room_code = f'edu-{uuid.uuid4().hex[:10]}'
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    try:
        max_p = max(2, min(500, int(data.get('maxParticipants') or 50)))
    except (TypeError, ValueError):
        max_p = 50

    engine = (data.get('engine') or 'builtin').strip().lower()
    if engine not in ('builtin', 'jitsi'):
        engine = 'builtin'

    sfu_domain = (data.get('sfuDomain') or 'meet.ffmuc.net').strip()
    sfu_domain = re.sub(r'^https?://', '', sfu_domain).strip('/') or 'meet.ffmuc.net'

    status = (data.get('status') or 'scheduled').strip().lower()
    if status not in ('scheduled', 'live', 'ended'):
        status = 'scheduled'

    conn = get_db()
    conn.execute("""
        INSERT INTO conferences (
            id, title, description, course_id, host_user_id, scheduled_at,
            max_participants, engine, sfu_domain, room_code, access_pin,
            allow_recording, mute_on_entry, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        conf_id,
        title,
        (data.get('description') or '').strip(),
        (data.get('courseId') or '').strip(),
        session.get('user_id') or '',
        (data.get('scheduledAt') or '').strip(),
        max_p,
        engine,
        sfu_domain,
        room_code,
        (data.get('accessPin') or '').strip(),
        1 if data.get('allowRecording', True) else 0,
        1 if data.get('muteOnEntry', True) else 0,
        status,
        now_str
    ))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'conferenceId': conf_id})


@app.route('/api/admin/conferences/<conf_id>', methods=['PUT', 'DELETE'])
@admin_required
def api_admin_manage_conference(conf_id):
    """Редактирование или удаление видеоконференции."""
    conn = get_db()
    existing = conn.execute('SELECT * FROM conferences WHERE id = ?', (conf_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({'error': 'Конференция не найдена'}), 404

    if request.method == 'DELETE':
        recs = conn.execute(
            'SELECT stored_name FROM conference_recordings WHERE conference_id = ?',
            (conf_id,)
        ).fetchall()
        for r in recs:
            p = os.path.join(UPLOAD_RECORDING_DIR, r['stored_name'])
            if os.path.isfile(p):
                os.remove(p)
        conn.execute('DELETE FROM conferences WHERE id = ?', (conf_id,))
        conn.commit()
        conn.close()
        with CONFERENCE_LOCK:
            CONFERENCE_ROOMS.pop(conf_id, None)
        return jsonify({'ok': True})

    data = request.get_json(silent=True) or {}
    try:
        max_p = max(2, min(500, int(data.get('maxParticipants', existing['max_participants']) or 50)))
    except (TypeError, ValueError):
        max_p = int(existing['max_participants'] or 50)

    engine = (data.get('engine', existing['engine']) or 'builtin').strip().lower()
    if engine not in ('builtin', 'jitsi'):
        engine = 'builtin'

    sfu_domain = (data.get('sfuDomain', existing['sfu_domain']) or 'meet.ffmuc.net').strip()
    sfu_domain = re.sub(r'^https?://', '', sfu_domain).strip('/') or 'meet.ffmuc.net'

    status = (data.get('status', existing['status']) or 'scheduled').strip().lower()
    if status not in ('scheduled', 'live', 'ended'):
        status = existing['status']

    conn.execute("""
        UPDATE conferences SET
            title = ?, description = ?, course_id = ?, scheduled_at = ?,
            max_participants = ?, engine = ?, sfu_domain = ?, access_pin = ?,
            allow_recording = ?, mute_on_entry = ?, status = ?
        WHERE id = ?
    """, (
        (data.get('title', existing['title']) or '').strip() or existing['title'],
        (data.get('description', existing['description']) or '').strip(),
        (data.get('courseId', existing['course_id']) or '').strip(),
        (data.get('scheduledAt', existing['scheduled_at']) or '').strip(),
        max_p,
        engine,
        sfu_domain,
        (data.get('accessPin', existing['access_pin']) or '').strip(),
        1 if data.get('allowRecording', existing['allow_recording']) else 0,
        1 if data.get('muteOnEntry', existing['mute_on_entry']) else 0,
        status,
        conf_id
    ))
    conn.commit()
    conn.close()

    if status == 'ended':
        with CONFERENCE_LOCK:
            room = _get_room_state_unlocked(conf_id)
            room['ended'] = True
            for pid in list(room['signals'].keys()):
                room['signals'][pid].append({'type': 'end_meeting', 'from': 'host'})
    elif status == 'live':
        with CONFERENCE_LOCK:
            room = _get_room_state_unlocked(conf_id)
            room['ended'] = False

    return jsonify({'ok': True})


@app.route('/api/conferences/<conf_id>/join', methods=['POST'])
@login_required
def api_conference_join(conf_id):
    """Подключение участника к видеоконференции с проверкой доступа, PIN-кода и лимита участников."""
    conn = get_db()
    user = get_current_user(conn)
    conf = conn.execute('SELECT * FROM conferences WHERE id = ?', (conf_id,)).fetchone()
    if not conf:
        conn.close()
        return jsonify({'error': 'Конференция не найдена'}), 404
    if not has_conference_access(conn, user, conf):
        conn.close()
        return jsonify({'error': 'Доступ к этой конференции закрыт'}), 403

    data = request.get_json(silent=True) or {}
    is_host = (user['role'] == 'admin')
    required_pin = (conf['access_pin'] or '').strip()
    if required_pin and not is_host:
        entered_pin = (data.get('pin') or '').strip()
        if entered_pin != required_pin:
            conn.close()
            return jsonify({'error': 'Неверный PIN-код комнаты'}), 403

    if conf['status'] == 'ended' and not is_host:
        conn.close()
        return jsonify({'error': 'Эта видеоконференция уже завершена организатором'}), 400

    # Организатор автоматически переводит комнату в статус 'live' при входе
    if is_host and conf['status'] != 'live':
        conn.execute("UPDATE conferences SET status = 'live' WHERE id = ?", (conf_id,))
        conn.commit()

    max_participants = int(conf['max_participants'] or 50)
    conn.close()

    peer_id = f'peer-{uuid.uuid4().hex[:10]}'
    now = time.time()

    with CONFERENCE_LOCK:
        room = _get_room_state_unlocked(conf_id)
        if is_host:
            room['ended'] = False
        if not is_host and len(room['peers']) >= max_participants:
            return jsonify({'error': f'Комната заполнена (лимит: {max_participants} участников)'}), 409

        # Адаптивный режим для 30+ участников: при > 10 участниках новые ученики входят как слушатели с правом поднять руку
        active_speakers = sum(1 for p in room['peers'].values() if p.get('canSpeak'))
        can_speak = True if is_host else (active_speakers < 12)
        mic_on = bool(data.get('micOn', not bool(conf['mute_on_entry']))) and can_speak
        cam_on = bool(data.get('camOn', False)) and can_speak

        room['peers'][peer_id] = {
            'peerId': peer_id,
            'userId': user['id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'isHost': is_host,
            'micOn': mic_on,
            'camOn': cam_on,
            'screenOn': False,
            'handRaised': False,
            'canSpeak': can_speak,
            'isRecording': False,
            'reaction': '',
            'reactionAt': 0,
            'joinedAt': now,
            'lastSeen': now
        }
        room['signals'][peer_id] = []
        peers_snapshot = sorted(
            room['peers'].values(),
            key=lambda p: (0 if p['isHost'] else 1, 0 if p['handRaised'] else 1, p['joinedAt'])
        )

    return jsonify({
        'ok': True,
        'peerId': peer_id,
        'canSpeak': can_speak,
        'peers': peers_snapshot
    })


@app.route('/api/conferences/<conf_id>/poll', methods=['POST'])
@login_required
def api_conference_poll(conf_id):
    """Пульс участника: обновляет статус, забирает WebRTC-сигналы, список участников и новые сообщения чата."""
    data = request.get_json(silent=True) or {}
    peer_id = (data.get('peerId') or '').strip()
    last_chat_id = int(data.get('lastChatId') or 0)
    if not peer_id:
        return jsonify({'error': 'Отсутствует peerId'}), 400

    now = time.time()
    with CONFERENCE_LOCK:
        room = _get_room_state_unlocked(conf_id)
        me = room['peers'].get(peer_id)
        if not me:
            return jsonify({'ok': False, 'kicked': True, 'ended': bool(room.get('ended'))}), 410

        me['lastSeen'] = now
        if 'micOn' in data:
            me['micOn'] = bool(data['micOn']) and bool(me['canSpeak'])
        if 'camOn' in data:
            me['camOn'] = bool(data['camOn']) and bool(me['canSpeak'])
        if 'screenOn' in data:
            me['screenOn'] = bool(data['screenOn']) and bool(me['canSpeak'])
        if 'handRaised' in data:
            me['handRaised'] = bool(data['handRaised'])
        if 'isRecording' in data:
            me['isRecording'] = bool(data['isRecording'])
        if data.get('reaction'):
            me['reaction'] = str(data['reaction'])[:8]
            me['reactionAt'] = now

        # Очищаем устаревшие реакции (> 5 сек)
        for p in room['peers'].values():
            if p.get('reaction') and now - p.get('reactionAt', 0) > 5:
                p['reaction'] = ''

        incoming_signals = room['signals'].get(peer_id, [])
        room['signals'][peer_id] = []

        peers_snapshot = sorted(
            room['peers'].values(),
            key=lambda p: (0 if p['isHost'] else 1, 0 if p['handRaised'] else 1, p['joinedAt'])
        )
        any_recording = any(p.get('isRecording') for p in room['peers'].values())
        ended = bool(room.get('ended'))
        my_can_speak = bool(me.get('canSpeak'))

    conn = get_db()
    chat_rows = conn.execute(
        'SELECT id, user_id, user_name, user_role, message, created_at FROM conference_chat WHERE conference_id = ? AND id > ? ORDER BY id ASC LIMIT 80',
        (conf_id, last_chat_id)
    ).fetchall()
    conn.close()

    chat_messages = [
        {
            'id': r['id'],
            'userId': r['user_id'],
            'userName': r['user_name'],
            'userRole': r['user_role'],
            'message': r['message'],
            'createdAt': r['created_at']
        }
        for r in chat_rows
    ]

    return jsonify({
        'ok': True,
        'ended': ended,
        'canSpeak': my_can_speak,
        'anyRecording': any_recording,
        'peers': peers_snapshot,
        'signals': incoming_signals,
        'chat': chat_messages
    })


@app.route('/api/conferences/<conf_id>/signal', methods=['POST'])
@login_required
def api_conference_signal(conf_id):
    """Передача WebRTC-сигналов (offer, answer, ice) между участниками."""
    data = request.get_json(silent=True) or {}
    from_peer = (data.get('from') or '').strip()
    to_peer = (data.get('to') or '').strip()
    sig_type = (data.get('type') or '').strip()
    payload = data.get('payload')

    if not from_peer or not to_peer or not sig_type:
        return jsonify({'error': 'Некорректные параметры сигнала'}), 400

    with CONFERENCE_LOCK:
        room = _get_room_state_unlocked(conf_id)
        if from_peer not in room['peers'] or to_peer not in room['peers']:
            return jsonify({'ok': False}), 200
        room['signals'].setdefault(to_peer, []).append({
            'from': from_peer,
            'type': sig_type,
            'payload': payload
        })
    return jsonify({'ok': True})


@app.route('/api/conferences/<conf_id>/host-action', methods=['POST'])
@admin_required
def api_conference_host_action(conf_id):
    """Управление участниками со стороны организатора (выдать/забрать слово, выкл. микрофон всем, исключить, завершить)."""
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip()
    target_peer = (data.get('targetPeerId') or '').strip()

    with CONFERENCE_LOCK:
        room = _get_room_state_unlocked(conf_id)
        if action == 'mute_all':
            for pid, p in room['peers'].items():
                if not p['isHost']:
                    p['micOn'] = False
                    room['signals'].setdefault(pid, []).append({'type': 'force_mute', 'from': 'host'})
        elif action == 'grant_speak' and target_peer in room['peers']:
            room['peers'][target_peer]['canSpeak'] = True
            room['peers'][target_peer]['handRaised'] = False
            room['signals'].setdefault(target_peer, []).append({'type': 'grant_speak', 'from': 'host'})
        elif action == 'revoke_speak' and target_peer in room['peers']:
            p = room['peers'][target_peer]
            if not p['isHost']:
                p['canSpeak'] = False
                p['micOn'] = False
                p['camOn'] = False
                p['screenOn'] = False
                room['signals'].setdefault(target_peer, []).append({'type': 'revoke_speak', 'from': 'host'})
        elif action == 'mute_peer' and target_peer in room['peers']:
            room['peers'][target_peer]['micOn'] = False
            room['signals'].setdefault(target_peer, []).append({'type': 'force_mute', 'from': 'host'})
        elif action == 'kick_peer' and target_peer in room['peers']:
            if not room['peers'][target_peer]['isHost']:
                room['peers'].pop(target_peer, None)
                room['signals'].pop(target_peer, None)
        elif action == 'end_meeting':
            room['ended'] = True
            for pid in list(room['signals'].keys()):
                room['signals'][pid].append({'type': 'end_meeting', 'from': 'host'})
            conn = get_db()
            conn.execute("UPDATE conferences SET status = 'ended' WHERE id = ?", (conf_id,))
            conn.commit()
            conn.close()
        else:
            return jsonify({'error': 'Неизвестное действие организатора'}), 400

    return jsonify({'ok': True})


@app.route('/api/conferences/<conf_id>/leave', methods=['POST'])
@login_required
def api_conference_leave(conf_id):
    """Корректный выход участника из комнаты."""
    data = request.get_json(silent=True) or {}
    peer_id = (data.get('peerId') or '').strip()
    if peer_id:
        with CONFERENCE_LOCK:
            room = _get_room_state_unlocked(conf_id)
            room['peers'].pop(peer_id, None)
            room['signals'].pop(peer_id, None)
    return jsonify({'ok': True})


@app.route('/api/conferences/<conf_id>/chat', methods=['POST'])
@login_required
def api_conference_chat_post(conf_id):
    """Отправка сообщения в чат видеоконференции."""
    data = request.get_json(silent=True) or {}
    msg = (data.get('message') or '').strip()
    if not msg:
        return jsonify({'error': 'Введите сообщение'}), 400
    msg = msg[:1500]

    conn = get_db()
    user = get_current_user(conn)
    conf = conn.execute('SELECT * FROM conferences WHERE id = ?', (conf_id,)).fetchone()
    if not conf or not has_conference_access(conn, user, conf):
        conn.close()
        return jsonify({'error': 'Нет доступа к конференции'}), 403

    now_str = datetime.now().strftime('%H:%M')
    cur = conn.execute(
        'INSERT INTO conference_chat (conference_id, user_id, user_name, user_role, message, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (conf_id, user['id'], user['name'], user['role'], msg, now_str)
    )
    chat_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'id': chat_id})


@app.route('/api/conferences/<conf_id>/recordings', methods=['GET', 'POST'])
@login_required
def api_conference_recordings(conf_id):
    """Список записей конференции или сохранение новой видеозаписи звонка на сервер."""
    conn = get_db()
    user = get_current_user(conn)
    conf = conn.execute('SELECT * FROM conferences WHERE id = ?', (conf_id,)).fetchone()
    if not conf or not has_conference_access(conn, user, conf):
        conn.close()
        return jsonify({'error': 'Нет доступа к конференции'}), 403

    if request.method == 'GET':
        rows = conn.execute(
            'SELECT * FROM conference_recordings WHERE conference_id = ? ORDER BY rowid DESC',
            (conf_id,)
        ).fetchall()
        out = []
        for r in rows:
            tok = generate_recording_token(r['id'], user['id'])
            out.append({
                'id': r['id'],
                'conferenceId': r['conference_id'],
                'title': r['title'],
                'fileSize': int(r['file_size'] or 0),
                'durationSec': int(r['duration_sec'] or 0),
                'recordedBy': r['recorded_by'] or '',
                'createdAt': r['created_at'] or '',
                'streamUrl': f"/api/conferences/recordings/{r['id']}/stream?token={tok}"
            })
        conn.close()
        return jsonify({'ok': True, 'recordings': out})

    # POST: загрузка видеозаписи звонка
    if user['role'] != 'admin' and not bool(conf['allow_recording']):
        conn.close()
        return jsonify({'error': 'Запись звонков отключена организатором'}), 403

    file = request.files.get('recording') or request.files.get('video') or request.files.get('file')
    if not file or not file.filename:
        conn.close()
        return jsonify({'error': 'Файл видеозаписи не передан'}), 400

    orig_name = (file.filename or 'recording.webm').strip()
    _, ext = os.path.splitext(orig_name.lower())
    if ext not in ALLOWED_RECORDING_EXTS:
        ext = '.webm'

    rec_id = f'rec-{uuid.uuid4().hex[:8]}'
    stored_name = f'{conf_id}_{rec_id}{ext}'
    save_path = os.path.join(UPLOAD_RECORDING_DIR, stored_name)
    file.save(save_path)
    file_size = os.path.getsize(save_path)

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    title = (request.form.get('title') or '').strip() or f"{conf['title']} — запись ({now_str})"
    try:
        duration_sec = max(0, int(float(request.form.get('durationSec') or 0)))
    except (TypeError, ValueError):
        duration_sec = 0

    conn.execute("""
        INSERT INTO conference_recordings (
            id, conference_id, title, stored_name, file_size, duration_sec, recorded_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (rec_id, conf_id, title, stored_name, file_size, duration_sec, user['name'], now_str))
    conn.commit()
    conn.close()

    tok = generate_recording_token(rec_id, user['id'])
    return jsonify({
        'ok': True,
        'recording': {
            'id': rec_id,
            'conferenceId': conf_id,
            'title': title,
            'fileSize': file_size,
            'durationSec': duration_sec,
            'recordedBy': user['name'],
            'createdAt': now_str,
            'streamUrl': f'/api/conferences/recordings/{rec_id}/stream?token={tok}'
        }
    })


@app.route('/api/conferences/recordings/<rec_id>/stream', methods=['GET'])
def api_stream_protected_recording(rec_id):
    """Защищённый потоковый просмотр записи видеозвонка (Range-чанки, HMAC-токен, защита от скачивания)."""
    fetch_dest = (request.headers.get('Sec-Fetch-Dest') or '').lower()
    if fetch_dest in ('document', 'iframe', 'object', 'embed'):
        abort(403)

    conn = get_db()
    rec = conn.execute('SELECT * FROM conference_recordings WHERE id = ?', (rec_id,)).fetchone()
    if not rec:
        conn.close()
        abort(404)
    conf = conn.execute('SELECT * FROM conferences WHERE id = ?', (rec['conference_id'],)).fetchone()
    user = get_current_user(conn)
    if not conf or not has_conference_access(conn, user, conf):
        conn.close()
        abort(403)

    token = request.args.get('token', '')
    if not verify_recording_token(token, rec_id, user['id'] if user else 'guest'):
        conn.close()
        abort(403)

    file_path = os.path.join(UPLOAD_RECORDING_DIR, rec['stored_name'])
    conn.close()
    if not os.path.isfile(file_path):
        abort(404)

    file_size = os.path.getsize(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith('video/'):
        mime_type = 'video/webm'

    range_header = request.headers.get('Range')
    max_chunk = 2 * 1024 * 1024

    if range_header:
        match = re.match(r'bytes=(\d*)-(\d*)', range_header.strip())
        if not match:
            abort(416)
        start = int(match.group(1)) if match.group(1) else 0
        if start >= file_size:
            abort(416)
        end = int(match.group(2)) if match.group(2) else min(start + max_chunk - 1, file_size - 1)
        end = min(end, start + max_chunk - 1, file_size - 1)
        length = end - start + 1
        with open(file_path, 'rb') as f:
            f.seek(start)
            data = f.read(length)
        resp = Response(data, status=206, mimetype=mime_type, direct_passthrough=True)
        resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(length)
    else:
        end = min(max_chunk - 1, file_size - 1)
        length = end + 1
        with open(file_path, 'rb') as f:
            data = f.read(length)
        status_code = 206 if length < file_size else 200
        resp = Response(data, status=status_code, mimetype=mime_type, direct_passthrough=True)
        if status_code == 206:
            resp.headers['Content-Range'] = f'bytes 0-{end}/{file_size}'
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(length)

    resp.headers['Content-Disposition'] = 'inline'
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@app.route('/api/admin/conferences/recordings/<rec_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_recording(rec_id):
    """Удаление видеозаписи конференции."""
    conn = get_db()
    rec = conn.execute('SELECT * FROM conference_recordings WHERE id = ?', (rec_id,)).fetchone()
    if not rec:
        conn.close()
        return jsonify({'error': 'Запись не найдена'}), 404
    p = os.path.join(UPLOAD_RECORDING_DIR, rec['stored_name'])
    if os.path.isfile(p):
        os.remove(p)
    conn.execute('DELETE FROM conference_recordings WHERE id = ?', (rec_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/admin/conferences/recordings/<rec_id>/attach-lesson', methods=['POST'])
@admin_required
def api_admin_attach_recording_to_lesson(rec_id):
    """Прикрепляет запись видеоконференции как защищённый видеоурок выбранного урока курса."""
    data = request.get_json(silent=True) or {}
    lesson_id = (data.get('lessonId') or '').strip()
    if not lesson_id:
        return jsonify({'error': 'Выберите урок курса'}), 400

    conn = get_db()
    rec = conn.execute('SELECT * FROM conference_recordings WHERE id = ?', (rec_id,)).fetchone()
    lesson = conn.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    if not rec or not lesson:
        conn.close()
        return jsonify({'error': 'Запись или урок не найдены'}), 404

    src_path = os.path.join(UPLOAD_RECORDING_DIR, rec['stored_name'])
    if not os.path.isfile(src_path):
        conn.close()
        return jsonify({'error': 'Файл записи отсутствует на диске'}), 404

    _, ext = os.path.splitext(rec['stored_name'])
    ext = ext or '.webm'
    new_stored = f'{lesson_id}_{uuid.uuid4().hex[:8]}{ext}'
    dst_path = os.path.join(UPLOAD_VIDEO_DIR, new_stored)
    shutil.copy2(src_path, dst_path)

    if lesson['video_stored_name']:
        old_v = os.path.join(UPLOAD_VIDEO_DIR, lesson['video_stored_name'])
        if os.path.isfile(old_v):
            os.remove(old_v)

    display_name = f"{rec['title']}{ext}"
    next_type = 'video' if lesson['content_type'] == 'text' else lesson['content_type']
    conn.execute(
        'UPDATE lessons SET video_filename = ?, video_stored_name = ?, content_type = ? WHERE id = ?',
        (display_name, new_stored, next_type, lesson_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'videoFileName': display_name})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
