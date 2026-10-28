"""Only explicit unsupported execution requests receive a local notice.

Every design/verification/repair analysis must go through the model. Archived
records are evidence in the model context, never a replacement for its answer.
"""
from .schemas import ChatDecision

UNSUPPORTED = {'重新验证当前设计', '按预置规格生成并验证'}


def normalize(text):
    return text.strip().rstrip('？?。！!')


def unsupported_reply(text):
    if normalize(text) in UNSUPPORTED:
        return ChatDecision(kind='answer', text='当前演示暂不支持现场重新验证或生成并验证。你可以向 AI 提问模块架构、当前验证结果或失败原因与修复记录。')
    return None
