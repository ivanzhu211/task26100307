"""输入条件的符号表示：字面量、合取、DNF，以及可满足性与见证构造。"""

from __future__ import annotations

from dataclasses import dataclass

from .model import CallerInput, Condition


@dataclass(frozen=True)
class Literal:
    """一个关于输入的原子命题或其否定。

    kind 为 "keyword" 时检查关键词集合是否包含 value；
    kind 为 "intent" 时检查意图是否等于 value。
    positive 为 False 表示取否定。
    """

    kind: str
    value: str
    positive: bool = True

    def negate(self) -> "Literal":
        return Literal(self.kind, self.value, not self.positive)


@dataclass(frozen=True)
class Conjunction:
    """若干字面量的合取，描述一类合法输入。"""

    literals: frozenset[Literal] = frozenset()

    def with_literal(self, lit: Literal) -> "Conjunction":
        return Conjunction(self.literals | {lit})

    def with_negated(self, lit: Literal) -> "Conjunction":
        return self.with_literal(lit.negate())


def condition_literal(cond: Condition) -> Literal:
    """把分支条件转换为正字面量。"""
    if cond.keyword is not None:
        return Literal("keyword", cond.keyword)
    return Literal("intent", cond.intent)


def conjunction_satisfiable(conj: Conjunction, intents: tuple[str, ...]) -> bool:
    """判断合取条件是否存在满足的合法输入。"""
    keyword_required: set[str] = set()
    keyword_forbidden: set[str] = set()
    intent_positive: set[str] = set()
    intent_negative: set[str] = set()
    for lit in conj.literals:
        if lit.kind == "keyword":
            (keyword_required if lit.positive else keyword_forbidden).add(lit.value)
        else:
            (intent_positive if lit.positive else intent_negative).add(lit.value)
    if keyword_required & keyword_forbidden:
        return False
    if len(intent_positive) > 1:
        return False
    if intent_positive & intent_negative:
        return False
    if not intent_positive and set(intents) <= intent_negative:
        return False
    return True


def witness_input(conj: Conjunction, intents: tuple[str, ...]) -> CallerInput:
    """为可满足的合取条件构造一份具体合法输入。"""
    keywords: set[str] = set()
    intent_positive: set[str] = set()
    intent_negative: set[str] = set()
    for lit in conj.literals:
        if lit.kind == "keyword":
            if lit.positive:
                keywords.add(lit.value)
        elif lit.positive:
            intent_positive.add(lit.value)
        else:
            intent_negative.add(lit.value)
    if intent_positive:
        intent = next(iter(intent_positive))
    else:
        intent = next(i for i in intents if i not in intent_negative)
    return CallerInput(keywords=frozenset(keywords), intent=intent)


def dnf_and_guard(
    dnf: list[Conjunction], guards: list[Literal]
) -> list[Conjunction]:
    """对 DNF 中每个合取依次追加守卫字面量，返回新的 DNF（不做可满足性过滤）。"""
    result: list[Conjunction] = []
    for conj in dnf:
        merged = conj
        for lit in guards:
            merged = merged.with_literal(lit)
        result.append(merged)
    return result
