"""Name generation requests shared by Faker and LLM backends."""
import asyncio
import re
from dataclasses import dataclass

from faker import Faker
from faker.config import AVAILABLE_LOCALES


MAX_NAMES = 50
LOCALES = {
    '中国': 'zh_CN', '中文': 'zh_CN', 'cn': 'zh_CN', 'zh': 'zh_CN',
    '英国': 'en_GB', '英文': 'en_GB', 'en': 'en_GB', 'uk': 'en_GB',
    '美国': 'en_US', 'us': 'en_US',
    '日本': 'ja_JP', '日语': 'ja_JP', 'jp': 'ja_JP', 'ja': 'ja_JP',
    '法国': 'fr_FR', 'fr': 'fr_FR', '德国': 'de_DE', 'de': 'de_DE',
    '韩国': 'ko_KR', 'kr': 'ko_KR', '俄罗斯': 'ru_RU', 'ru': 'ru_RU',
    '意大利': 'it_IT', 'it': 'it_IT', '西班牙': 'es_ES', 'es': 'es_ES',
}
USAGE = '用法：.取名 中国 5（或 .name 中国 5）；LLM 模式也支持 .取名 给我五个维多利亚时代的英国女性名字'


@dataclass(frozen=True)
class NameRequest:
    requirement: str
    nationality: str = ''
    count: int = 5
    sex: str = ''


def parse_name_request(text: str) -> NameRequest:
    text = text.strip()
    if not text:
        return NameRequest('生成 5 个中国人名。', '中国')
    parts = text.split()
    if len(parts) in (2, 3) and re.fullmatch(r'[+-]?\d+', parts[1]):
        count = int(parts[1])
        if not 1 <= count <= MAX_NAMES:
            raise ValueError(f'取名数量须为 1～{MAX_NAMES}。')
        sex = parts[2] if len(parts) == 3 else ''
        if sex and sex not in ('男', '女'):
            return NameRequest(text)
        return NameRequest(f'生成 {count} 个符合 {parts[0]} 国籍/语言文化的{sex}性人名。' if sex
                           else f'生成 {count} 个符合 {parts[0]} 国籍/语言文化的人名。',
                           parts[0], count, sex)
    if len(parts) == 1 and (parts[0].lower() in LOCALES or parts[0] in AVAILABLE_LOCALES):
        return NameRequest(f'生成 5 个符合 {parts[0]} 国籍/语言文化的人名。', parts[0])
    return NameRequest(text)


def generate_faker_names(request: NameRequest) -> list[str]:
    if not request.nationality:
        raise ValueError('Faker 模式不支持自由需求；请使用“国籍 数量”，或在插件配置中切换为 llm。')
    locale = LOCALES.get(request.nationality.lower(), request.nationality)
    if locale not in AVAILABLE_LOCALES:
        raise ValueError('Faker 不支持该国籍，请使用中国、英国、美国、日本等，或有效的 Faker locale；也可切换为 llm。')
    fake = Faker(locale)
    method = fake.name_male if request.sex == '男' else fake.name_female if request.sex == '女' else fake.name
    return [method() for _ in range(request.count)]


async def generate_llm_names(context, request: NameRequest, provider_id: str = '') -> str:
    provider = context.get_provider_by_id(provider_id) if provider_id else context.get_using_provider()
    if provider is None:
        raise ValueError('未找到取名模型，请在 AstrBot 配置 LLM，并检查 name_llm_provider_id。')
    response = await asyncio.wait_for(provider.text_chat(
        prompt=request.requirement,
        contexts=[],
        system_prompt=(
            '你是跑团角色取名助手。根据用户的国籍、语言、时代、性别和风格要求生成虚构角色名字。'
            '按用户指定数量生成；未指定数量时生成 5 个，最多生成 50 个。'
            '使用中文回复，外国名字可附原文；用编号列表列出名字，必要时附简短说明。'
            '只回答取名需求，不调用工具。'
        ),
    ), timeout=60)
    result = getattr(response, 'completion_text', '')
    if not isinstance(result, str) or not result.strip():
        raise ValueError('模型未返回名字，请稍后重试或检查模型配置。')
    return result.strip()
