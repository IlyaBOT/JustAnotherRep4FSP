from __future__ import annotations

import re
from dataclasses import dataclass

from .seed_data import (
    CONTACTS,
    FAQ_ENTRIES,
    MAIN_MENU,
    SOCIAL_CONTRACT_STAGE_ONE_DOCUMENTS,
    SOCIAL_CONTRACT_STAGE_TWO_DOCUMENTS,
)


@dataclass
class BotMessage:
    text: str
    buttons: list[dict] | None = None
    meta: dict | None = None


class BotEngine:
    def welcome_messages(self) -> list[BotMessage]:
        return [
            BotMessage(
                text=(
                    "Здравствуйте. Я чат-бот навигатор «СВОй». Помогу с мерами поддержки, "
                    "социальным контрактом и связью со специалистом."
                )
            ),
            BotMessage(
                text="Пожалуйста, выберите категорию:",
                buttons=[
                    {"label": "Ветеран СВО", "value": "persona:veteran"},
                    {"label": "Член семьи ветерана СВО", "value": "persona:family"},
                ],
            ),
        ]

    def handle(self, text: str, state: dict | None) -> tuple[list[BotMessage], dict]:
        state = dict(state or {})
        normalized = text.strip()
        lowered = normalized.lower()

        if lowered in {"sc:upload_documents", "загрузка документов", "загрузить документы", "прикрепить документы"}:
            state["show_upload_button"] = True
        elif lowered.startswith(("menu:", "sc:", "consult:", "faq:", "persona:")) or lowered in {
            "/start",
            "start",
            "привет",
            "здравствуйте",
            "начать",
            "меню",
            "главное меню",
            "назад",
            "consult",
            "консультация",
        }:
            state["show_upload_button"] = False

        pending = state.get("pending")
        if pending == "contact_full_name":
            state["lead_full_name"] = normalized
            state["pending"] = "contact_phone"
            return [BotMessage(text="Укажите, пожалуйста, номер телефона для обратной связи.")], state

        if pending == "contact_phone":
            state["lead_phone"] = normalized
            state["pending"] = "contact_message"
            return [BotMessage(text="Если хотите, добавьте комментарий к заявке. Или отправьте «-», если комментарий не нужен.")], state

        if pending == "contact_message":
            state["lead_message"] = None if normalized == "-" else normalized
            state["pending"] = None
            state["create_contact_request"] = True
            return [
                BotMessage(text="Принято. Сохраняю заявку и передаю её специалисту."),
                BotMessage(text="После этого можно вернуться в меню.", buttons=self._menu_buttons()),
            ], state

        if lowered in {"/start", "start", "привет", "здравствуйте", "начать"}:
            return self.welcome_messages(), state

        if lowered in {"меню", "главное меню", "назад"}:
            return [BotMessage(text="Главное меню:", buttons=self._menu_buttons())], state

        if lowered.startswith("persona:"):
            persona = lowered.split(":", 1)[1]
            state["persona"] = persona
            persona_title = "ветеран СВО" if persona == "veteran" else "член семьи ветерана СВО"
            return [
                BotMessage(text=f"Категория выбрана: {persona_title}."),
                BotMessage(text="Главное меню:", buttons=self._menu_buttons()),
            ], state

        if lowered == "menu:social_contract":
            state["flow"] = "social_contract"
            return [
                BotMessage(
                    text=(
                        "В 2026 году доступны 2000 социальных контрактов по 350 000 рублей. "
                        "Поможем сориентироваться по документам и следующим шагам."
                    )
                ),
                BotMessage(
                    text="Вы уже начали собирать документы?",
                    buttons=[
                        {"label": "Нужен бизнес-план", "value": "sc:business_plan"},
                        {"label": "У меня есть вопросы", "value": "sc:questions"},
                        {"label": "Как государство может помочь?", "value": "sc:state_help"},
                        {"label": "Список документов", "value": "sc:checklist"},
                        {"label": "Загрузка документов", "value": "sc:upload_documents"},
                    ],
                ),
            ], state

        if lowered == "sc:business_plan":
            return [
                BotMessage(
                    text=(
                        "Для бизнес-плана обычно готовят: данные заявителя, описание проекта, "
                        "маркетинговый план, смету расходов, финансовый план и приложения."
                    )
                ),
                BotMessage(
                    text="Если вы уже готовите пакет на соцконтракт, могу сразу показать список документов.",
                    buttons=[
                        {"label": "Список документов", "value": "sc:checklist"},
                        {"label": "Загрузка документов", "value": "sc:upload_documents"},
                        {"label": "Какую систему налогообложения выбрать?", "value": "faq:налогообложение"},
                        {"label": "Как составить смету?", "value": "faq:смета"},
                    ],
                ),
            ], state

        if lowered == "sc:questions":
            return [
                BotMessage(
                    text="Выберите частый вопрос или напишите свой текстом:",
                    buttons=[
                        {"label": "Какие данные указать о себе?", "value": "faq:какие данные"},
                        {"label": "Что такое ОКВЭД?", "value": "faq:оквэд"},
                        {"label": "Какую рекламу выбрать?", "value": "faq:реклама"},
                        {"label": "Что писать в описании проекта?", "value": "faq:описание проекта"},
                    ],
                )
            ], state

        if lowered == "sc:state_help":
            return [
                BotMessage(
                    text=(
                        "Центр «Мой бизнес» помогает с бизнес-планированием, микрозаймами, "
                        "гарантийной поддержкой, программой «СВОяТема», популяризацией продукции "
                        "и другими мерами господдержки."
                    )
                ),
                BotMessage(text="Что показать дальше?", buttons=[
                    {"label": "Меры поддержки", "value": "menu:support"},
                    {"label": "СВОяТема", "value": "menu:svoyatema"},
                    {"label": "Консультация", "value": "menu:consult"},
                ]),
            ], state

        if lowered == "sc:checklist":
            return self._social_contract_checklist_messages(state), state

        if lowered in {"sc:upload_documents", "загрузка документов", "загрузить документы", "прикрепить документы"}:
            return self._social_contract_upload_messages(state), state

        if lowered == "menu:support":
            return [
                BotMessage(
                    text=(
                        "Доступны меры поддержки: сертификация и стандартизация, программа «Быстрый старт», "
                        "регистрация товарного знака, участие в выставках и бизнес-миссиях, полиграфия, "
                        "гарантийная поддержка, аренда рабочих пространств и оборудования."
                    )
                ),
                BotMessage(
                    text="Также доступны финансовые продукты через АНО «МКК ДНР».",
                    buttons=[
                        {"label": "Финансовые меры", "value": "faq:микрокредит"},
                        {"label": "Как получить меру поддержки?", "value": "faq:как получить"},
                        {"label": "Консультация", "value": "menu:consult"},
                    ],
                ),
            ], state

        if lowered == "menu:svoyatema":
            return [
                BotMessage(
                    text=(
                        "«СВОяТема!» — это проект для ветеранов СВО и членов их семей: "
                        "разбор бизнес-идеи, подбор мер поддержки, образовательные мероприятия "
                        "и сопровождение бизнес-проекта."
                    )
                ),
                BotMessage(text="Можно перейти к специалисту или вернуться в меню.", buttons=[
                    {"label": "Оставить заявку", "value": "consult:leave_request"},
                    {"label": "Главное меню", "value": "menu:root"},
                ]),
            ], state

        if lowered in {"menu:consult", "consult", "консультация"}:
            return [
                BotMessage(
                    text=(
                        "Я могу предложить три варианта: оставить заявку, показать контакты или подсказать адреса для визита."
                    ),
                    buttons=[
                        {"label": "Оставить заявку", "value": "consult:leave_request"},
                        {"label": "Контакты для связи", "value": "consult:contacts"},
                        {"label": "Записаться / прийти в центр", "value": "consult:visit"},
                    ],
                )
            ], state

        if lowered == "consult:leave_request":
            state["pending"] = "contact_full_name"
            return [BotMessage(text="Хорошо. Укажите, пожалуйста, ФИО полностью.")], state

        if lowered == "consult:contacts":
            return [BotMessage(text=self._contacts_text(), buttons=self._menu_buttons())], state

        if lowered == "consult:visit":
            return [
                BotMessage(
                    text=(
                        f"Вы можете обратиться лично:\n"
                        f"• {CONTACTS['donetsk']}\n"
                        f"• {CONTACTS['mariupol']}\n\n"
                        f"Телефоны: {CONTACTS['phone_main']}, {CONTACTS['phone_mariupol']}\n"
                        f"Email: {CONTACTS['email']}"
                    ),
                    buttons=[
                        {"label": "Оставить заявку", "value": "consult:leave_request"},
                        {"label": "Главное меню", "value": "menu:root"},
                    ],
                )
            ], state

        if lowered == "menu:root":
            return [BotMessage(text="Главное меню:", buttons=self._menu_buttons())], state

        faq_answer = self._search_faq(lowered)
        if faq_answer:
            return [BotMessage(text=faq_answer, buttons=self._menu_buttons())], state

        return [
            BotMessage(
                text=(
                    "Я пока не нашёл точный ответ. Попробуйте выбрать раздел меню или оставьте заявку специалисту."
                ),
                buttons=[
                    {"label": "Главное меню", "value": "menu:root"},
                    {"label": "Оставить заявку", "value": "consult:leave_request"},
                    {"label": "Контакты", "value": "consult:contacts"},
                ],
            )
        ], state

    def _contacts_text(self) -> str:
        return (
            f"Контакты Центра «Мой бизнес»:\n"
            f"• Телефон: {CONTACTS['phone_main']}\n"
            f"• Доп. телефон: {CONTACTS['phone_mariupol']}\n"
            f"• Email: {CONTACTS['email']}\n"
            f"• Донецк: {CONTACTS['donetsk']}\n"
            f"• Мариуполь: {CONTACTS['mariupol']}\n"
            f"• Сайт: {CONTACTS['site']}"
        )

    def _menu_buttons(self) -> list[dict]:
        return MAIN_MENU

    def _social_contract_document_list_text(self) -> str:
        stage_one = "\n".join(f"• {item}" for item in SOCIAL_CONTRACT_STAGE_ONE_DOCUMENTS)
        stage_two = "\n".join(f"• {item}" for item in SOCIAL_CONTRACT_STAGE_TWO_DOCUMENTS)

        return (
            "Этап 1. Для рекомендации в фонде «Защитники Отечества»:\n"
            f"{stage_one}\n\n"
            "Этап 2. Для подачи в орган соцзащиты:\n"
            f"{stage_two}\n\n"
            "Часть документов нужна не всем. Ориентируйтесь на свою ситуацию."
        )

    def _social_contract_checklist_messages(self, state: dict) -> list[BotMessage]:
        return [
            BotMessage(
                text=(
                    "Вот примерный список документов, которые обычно готовят для социального контракта.\n\n"
                    f"{self._social_contract_document_list_text()}"
                ),
                buttons=[
                    {"label": "Загрузка документов", "value": "sc:upload_documents"},
                    {"label": "Нужен бизнес-план", "value": "sc:business_plan"},
                    {"label": "Консультация", "value": "menu:consult"},
                ],
                meta={"show_upload_button": bool(state.get("show_upload_button"))},
            )
        ]

    def _social_contract_upload_messages(self, state: dict) -> list[BotMessage]:
        state["show_upload_button"] = True

        return [
            BotMessage(
                text=(
                    "Для примера можно подготовить и загрузить такие документы.\n\n"
                    f"{self._social_contract_document_list_text()}"
                ),
                meta={"show_upload_button": True},
            ),
            BotMessage(
                text=(
                    "Когда будете готовы, нажмите кнопку «Загрузить файлы» рядом с отправкой сообщения. "
                    "После нажатия «Отправить» файлы уйдут на сервер, а я отвечу по факту загрузки. "
                    "При этом документы всё равно не сохраняются в базе данных."
                ),
                buttons=[
                    {"label": "Список документов", "value": "sc:checklist"},
                    {"label": "Консультация", "value": "menu:consult"},
                ],
                meta={"show_upload_button": True},
            ),
        ]

    def _search_faq(self, query: str) -> str | None:
        raw = query.removeprefix("faq:").strip()
        tokens = {token for token in re.split(r"\W+", raw) if len(token) > 1}
        if not tokens and raw:
            tokens = {raw}

        best_score = 0
        best_answer = None
        for entry in FAQ_ENTRIES:
            haystack = " ".join([entry["title"], *entry["keywords"]]).lower()
            score = sum(1 for token in tokens if token in haystack)
            if raw and raw in haystack:
                score += 2
            if score > best_score:
                best_score = score
                best_answer = entry["answer"]

        if best_score > 0:
            return best_answer
        return None

    def handle_uploaded_documents(
        self,
        files: list[dict],
        state: dict | None,
        comment: str | None = None,
    ) -> tuple[list[BotMessage], dict]:
        state = dict(state or {})
        state["show_upload_button"] = True

        file_names = [file["name"] for file in files if file.get("name")]
        recognized = self._recognize_uploaded_documents(file_names)
        missing = [item for item in self._upload_document_targets() if item not in recognized]

        uploaded_list = "\n".join(f"• {name}" for name in file_names)
        recognized_text = (
            "По названиям файлов я распознал такие документы:\n"
            + "\n".join(f"• {item}" for item in recognized)
            if recognized
            else "По названиям файлов я не смог точно определить тип документов, но загрузку принял."
        )
        missing_text = (
            "Для полного пакета обычно ещё проверяют:\n"
            + "\n".join(f"• {item}" for item in missing[:5])
            if missing
            else "По базовому списку у вас уже выглядит собранным основной пакет документов."
        )
        comment_text = f"Комментарий к отправке: {comment}\n\n" if comment else ""

        return [
            BotMessage(
                text=(
                    f"{comment_text}Принял файлы:\n"
                    f"{uploaded_list}\n\n"
                    f"{recognized_text}\n\n"
                    f"{missing_text}\n\n"
                    "Файлы отправлены на сервер, но в этой версии не сохраняются в базе данных."
                ),
                buttons=[
                    {"label": "Загрузить ещё документы", "value": "sc:upload_documents"},
                    {"label": "Список документов", "value": "sc:checklist"},
                    {"label": "Консультация", "value": "menu:consult"},
                ],
                meta={"show_upload_button": True},
            )
        ], state

    def _upload_document_targets(self) -> list[str]:
        return [
            "Паспорт",
            "СНИЛС",
            "Удостоверение ветерана боевых действий",
            "Свидетельство о браке",
            "Справка МСЭ",
            "Рекомендация фонда «Защитники Отечества»",
            "Бизнес-план",
            "Справка из Центра занятости",
            "Документы на помещение",
            "Реквизиты счёта",
        ]

    def _recognize_uploaded_documents(self, file_names: list[str]) -> list[str]:
        catalog = {
            "Паспорт": ("паспорт", "passport"),
            "СНИЛС": ("снилс", "snils"),
            "Удостоверение ветерана боевых действий": ("ветеран", "боевых", "удостовер"),
            "Свидетельство о браке": ("брак", "свидетельство"),
            "Справка МСЭ": ("мсэ", "инвалид"),
            "Рекомендация фонда «Защитники Отечества»": ("рекомендац", "защитник"),
            "Бизнес-план": ("бизнес", "план", "business"),
            "Справка из Центра занятости": ("занятост", "безработ", "ищущ"),
            "Документы на помещение": ("аренд", "помещен", "собствен", "гарантийн"),
            "Реквизиты счёта": ("счет", "счёт", "реквизит", "bank"),
        }

        normalized_names = [name.lower().replace("ё", "е") for name in file_names]
        recognized: list[str] = []
        for label, keywords in catalog.items():
            if any(any(keyword in name for keyword in keywords) for name in normalized_names):
                recognized.append(label)
        return recognized
