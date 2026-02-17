"""
Система памяти: MemoryItem, AgentMemorySystem.
"""

import re
from dataclasses import dataclass, asdict
from datetime import datetime

from colorama import Fore, Style

from config import (
    SHORT_TERM_MEMORY, LONG_TERM_MEMORY,
    COMPRESSION_THRESHOLD, IMPORTANCE_DECAY_FACTOR, EPISODE_GAP_TICKS,
)
from agent_registry import agent_registry
from llm_client import llm_chat
from vector_memory import VectorMemoryLayer
import chroma_storage


@dataclass
class MemoryItem:
    tick: int
    speaker: str
    text: str
    timestamp: str
    importance: float = 0.5
    speaker_id: str = ""
    addressed_to: str = ""
    addressed_to_id: str = ""
    is_event: bool = False
    is_action_result: bool = False

    def to_dict(self):
        return asdict(self)


class AgentMemorySystem:
    def __init__(self, agent_id: str, user_id: str = "", registry: 'AgentRegistry' = None):  # noqa: F821
        self.agent_id = agent_id
        self.user_id = user_id
        self._registry = registry  # Изолированный реестр сессии (если None — глобальный)
        self.short_term: list[MemoryItem] = []
        self.long_term: list[MemoryItem] = []
        self.completed_actions: list[str] = []
        self.pending_questions: list[dict] = []
        self.group_decisions: list[dict] = []  # решения группы и собственные предложения
        self._memories_since_save = 0
        self._autosave_interval = 1
        self.vector_layer = VectorMemoryLayer(agent_id, user_id=user_id)
        self.load_from_db()

    def _get_registry(self):
        """Get agent registry (session-scoped or global fallback)."""
        if self._registry is not None:
            return self._registry
        return agent_registry

    def add_memory(self, tick: int, speaker: str, text: str, importance: float = 0.5,
                   addressed_to: str = "", addressed_to_id: str = "",
                   speaker_id: str = "",
                   is_event: bool = False, is_action_result: bool = False):
        if not speaker_id and speaker:
            speaker_id = self._get_registry().get_id(speaker) or ""

        memory = MemoryItem(
            tick=tick, speaker=speaker, text=text,
            timestamp=datetime.now().isoformat(),
            importance=importance,
            speaker_id=speaker_id,
            addressed_to=addressed_to,
            addressed_to_id=addressed_to_id,
            is_event=is_event,
            is_action_result=is_action_result,
        )

        self.short_term.append(memory)
        self._memories_since_save += 1

        # Параллельно сохраняем в векторную БД
        self.vector_layer.add_document(
            text=text, tick=tick, importance=importance,
            is_event=is_event, speaker=speaker, speaker_id=speaker_id,
        )

        total_size = len(self.short_term) + len(self.long_term)
        if total_size >= COMPRESSION_THRESHOLD:
            self._smart_compress()
        elif len(self.short_term) > SHORT_TERM_MEMORY:
            oldest = self.short_term.pop(0)
            if oldest.importance > 0.6 or oldest.is_event or oldest.is_action_result:
                self._consolidate_to_long_term(oldest)

        if self._memories_since_save >= self._autosave_interval:
            self.save_to_db()
            self._memories_since_save = 0

    def add_group_decision(self, tick: int, proposer: str, decision: str, proposer_id: str = ""):
        """Записать решение группы или предложение агента."""
        self.group_decisions.append({
            "tick": tick, "proposer": proposer, "proposer_id": proposer_id,
            "decision": decision[:200],
        })
        if len(self.group_decisions) > 15:
            self.group_decisions = self.group_decisions[-15:]

    def get_group_decisions_text(self) -> str:
        """Форматировать решения группы для промпта."""
        if not self.group_decisions:
            return ""
        lines = ["═══ ПРИНЯТЫЕ РЕШЕНИЯ И ПРЕДЛОЖЕНИЯ (НЕ ПРОТИВОРЕЧЬ!) ═══"]
        for d in self.group_decisions[-8:]:
            proposer_name = self._get_registry().get_name(d.get('proposer_id', '')) if d.get('proposer_id') else d['proposer']
            lines.append(f"  [тик {d['tick']}] {proposer_name}: {d['decision']}")
        lines.append("--- Не предлагай действия, противоречащие этим решениям!")
        lines.append("--- Если ты сам предлагал что-то -- ПОМНИ об этом и не делай наоборот!\n")
        return "\n".join(lines)

    def record_action(self, action_text: str):
        """Записать выполненное действие."""
        self.completed_actions.append(action_text.lower().strip()[:100])
        if len(self.completed_actions) > 20:
            self.completed_actions = self.completed_actions[-20:]

    def has_done_similar(self, action_text: str) -> bool:
        """Проверить, делал ли агент уже подобное."""
        from utils import text_similarity
        action_lower = action_text.lower().strip()
        for prev in self.completed_actions:
            if text_similarity(action_lower, prev) > 0.5:
                return True
        return False

    def add_pending_question(self, tick: int, from_agent: str, question: str, from_id: str = ""):
        if not from_id and from_agent:
            from_id = self._get_registry().get_id(from_agent) or ""
        self.pending_questions.append({
            "tick": tick, "from": from_agent, "from_id": from_id, "question": question[:200]
        })
        if len(self.pending_questions) > 3:
            self.pending_questions = self.pending_questions[-3:]

    def get_pending_questions_text(self) -> str:
        if not self.pending_questions:
            return ""
        lines = ["═══ ТЕБЕ ЗАДАЛИ ВОПРОСЫ / ОБРАТИЛИСЬ К ТЕБЕ ═══"]
        for q in self.pending_questions:
            from_id = q.get('from_id', '')
            display_name = self._get_registry().get_name(from_id) if from_id else q['from']
            lines.append(f"  {display_name} (тик {q['tick']}): {q['question']}")
        lines.append("ОБЯЗАТЕЛЬНО ответь на эти вопросы или отреагируй!\n")
        return "\n".join(lines)

    def clear_pending_questions(self):
        self.pending_questions = []

    def _consolidate_to_long_term(self, memory: MemoryItem):
        self.long_term.append(memory)
        if len(self.long_term) > LONG_TERM_MEMORY:
            removable = [m for m in self.long_term if not m.is_event and not m.is_action_result]
            if removable:
                removable.sort(key=lambda m: m.importance)
                to_remove = removable[0]
                self.long_term.remove(to_remove)
            else:
                self.long_term.sort(key=lambda m: m.importance, reverse=True)
                self.long_term = self.long_term[:LONG_TERM_MEMORY]

    def _smart_compress(self):
        """Компрессия — реально уменьшает память."""
        all_memories = self.short_term + self.long_term
        if len(all_memories) < COMPRESSION_THRESHOLD:
            return

        print(f"{Fore.YELLOW}Сжатие памяти агента {self.agent_id} ({len(all_memories)} элементов)...{Style.RESET_ALL}")

        target_size = int(COMPRESSION_THRESHOLD * 0.6)
        fresh_count = min(10, len(all_memories) // 3)
        fresh_memories = all_memories[-fresh_count:]
        older_memories = all_memories[:-fresh_count]

        true_events = [m for m in older_memories if m.is_event]
        true_events.sort(key=lambda m: m.tick, reverse=True)
        critical_memories = true_events[:8]
        critical_set = set(id(m) for m in critical_memories)

        regular_memories = [m for m in older_memories if id(m) not in critical_set]

        current_tick = max((m.tick for m in all_memories), default=0)
        regular_memories.sort(
            key=lambda m: self._decayed_importance(m, current_tick),
            reverse=True
        )

        slots_for_regular = max(target_size - len(fresh_memories) - len(critical_memories), 5)
        top_important = regular_memories[:slots_for_regular]

        remaining = regular_memories[slots_for_regular:]
        summary_memories = []

        if len(remaining) > 5:
            remaining_sorted = sorted(remaining, key=lambda m: m.tick)
            episodes: list[list[MemoryItem]] = []
            current_episode: list[MemoryItem] = [remaining_sorted[0]]

            for mem in remaining_sorted[1:]:
                if mem.tick - current_episode[-1].tick <= EPISODE_GAP_TICKS:
                    current_episode.append(mem)
                else:
                    episodes.append(current_episode)
                    current_episode = [mem]
            episodes.append(current_episode)

            for episode in episodes[:4]:
                if len(episode) < 2:
                    continue
                episode_text = "\n".join([
                    f"[тик {m.tick}] [{m.speaker}]: {m.text[:80]}" for m in episode
                ])
                tick_range = f"{episode[0].tick}-{episode[-1].tick}"
                prompt = [
                    {
                        "role": "system",
                        "content": (
                            f"Сожми эпизод диалога (тики {tick_range}) в 1-2 ключевых пункта. "
                            "Сохрани: кто что СДЕЛАЛ, результаты, решения. "
                            "Каждый пункт — 1 короткое предложение. ТОЛЬКО русский, БЕЗ тегов."
                        )
                    },
                    {"role": "user", "content": f"Эпизод:\n{episode_text}\n\nКлючевые моменты:"}
                ]
                summary = llm_chat(prompt, temperature=0.3)
                if summary:
                    summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL | re.IGNORECASE)
                    summary = re.sub(r'</?think>', '', summary, flags=re.IGNORECASE)
                    summary_memories.append(MemoryItem(
                        tick=episode[-1].tick,
                        speaker="[СВОДКА]", text=f"[тики {tick_range}] {summary[:250]}",
                        timestamp=datetime.now().isoformat(), importance=0.65,
                        is_event=False, is_action_result=False,
                    ))

        new_long_term = critical_memories + top_important
        for sm in summary_memories:
            new_long_term.append(sm)

        old_size = len(all_memories)
        self.short_term = fresh_memories
        self.long_term = new_long_term
        new_size = len(self.short_term) + len(self.long_term)

        print(f"{Fore.GREEN}Память сжата: {old_size} -> {new_size} элементов{Style.RESET_ALL}")
        print(f"{Fore.CYAN}  События: {len(critical_memories)} | Важные: {len(top_important)} | Свежие: {len(fresh_memories)} | Сводки эпизодов: {len(summary_memories)}{Style.RESET_ALL}")
        self.save_to_db()

    def consolidate_before_rename(self, old_name: str, new_name: str):
        """Принудительная группировка перед переименованием агента."""
        all_memories = self.short_term + self.long_term
        affected = [m for m in all_memories
                    if old_name.lower() in m.text.lower()
                    or m.speaker.lower() == old_name.lower()]

        if not affected:
            return

        print(f"{Fore.YELLOW}Консолидация памяти перед переименованием "
              f"{old_name} -> {new_name} ({len(affected)} записей)...{Style.RESET_ALL}")

        affected_sorted = sorted(affected, key=lambda m: m.tick)
        episodes: list[list[MemoryItem]] = []
        current_episode: list[MemoryItem] = [affected_sorted[0]]
        for mem in affected_sorted[1:]:
            if mem.tick - current_episode[-1].tick <= EPISODE_GAP_TICKS:
                current_episode.append(mem)
            else:
                episodes.append(current_episode)
                current_episode = [mem]
        episodes.append(current_episode)

        summary_memories = []
        for episode in episodes[:3]:
            episode_text = "\n".join([
                f"[тик {m.tick}] [{m.speaker}]: {m.text[:80]}" for m in episode
            ])
            tick_range = f"{episode[0].tick}-{episode[-1].tick}"
            prompt = [
                {
                    "role": "system",
                    "content": (
                        f"Персонаж '{old_name}' переименован в '{new_name}'. "
                        f"Сожми эпизод (тики {tick_range}) в 1-2 предложения, "
                        f"заменив все упоминания '{old_name}' на '{new_name}'. "
                        "Сохрани ключевые действия и решения. ТОЛЬКО русский, БЕЗ тегов."
                    )
                },
                {"role": "user", "content": f"Эпизод:\n{episode_text}\n\nСводка:"}
            ]
            summary = llm_chat(prompt, temperature=0.3)
            if summary:
                summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL | re.IGNORECASE)
                summary = re.sub(r'</?think>', '', summary, flags=re.IGNORECASE)
                summary_memories.append(MemoryItem(
                    tick=episode[-1].tick,
                    speaker="[СВОДКА]",
                    text=f"[{old_name}→{new_name}] {summary[:250]}",
                    timestamp=datetime.now().isoformat(), importance=0.7,
                    is_event=False, is_action_result=False,
                ))

        affected_ids = set(id(m) for m in affected)
        self.short_term = [m for m in self.short_term if id(m) not in affected_ids]
        self.long_term = [m for m in self.long_term if id(m) not in affected_ids]
        self.long_term.extend(summary_memories)

        for mem in self.short_term + self.long_term:
            if mem.speaker == old_name:
                mem.speaker = new_name

        self.save_to_db()
        print(f"{Fore.GREEN}Консолидация завершена: {len(affected)} записей -> "
              f"{len(summary_memories)} сводок{Style.RESET_ALL}")

    def get_recent_context(self, n: int = SHORT_TERM_MEMORY) -> list[MemoryItem]:
        return self.short_term[-n:]

    def _decayed_importance(self, memory: MemoryItem, current_tick: int = None) -> float:
        """Temporal decay: важность убывает со временем."""
        if current_tick is None:
            current_tick = max(
                (m.tick for m in self.short_term + self.long_term),
                default=0
            )
        age = max(current_tick - memory.tick, 0)
        factor = IMPORTANCE_DECAY_FACTOR if not memory.is_event else (IMPORTANCE_DECAY_FACTOR ** 0.5)
        return memory.importance * (factor ** age)

    def get_relevant_long_term(self, n: int = 5) -> list[MemoryItem]:
        """Приоритет — события и результаты действий, с temporal decay."""
        current_tick = max(
            (m.tick for m in self.short_term + self.long_term),
            default=0
        )
        sorted_memories = sorted(self.long_term, key=lambda m: (
            m.is_event or m.is_action_result,
            self._decayed_importance(m, current_tick)
        ), reverse=True)
        return sorted_memories[:n]

    def format_for_prompt(self) -> str:
        context_parts = []

        # Решения группы — критически важно для консистентности
        decisions_text = self.get_group_decisions_text()
        if decisions_text:
            context_parts.append(decisions_text)

        long_term_relevant = self.get_relevant_long_term(5)
        if long_term_relevant:
            context_parts.append("═══ ВАЖНЫЕ СОБЫТИЯ ИЗ ПРОШЛОГО ═══")
            for mem in long_term_relevant:
                prefix = ""
                if mem.is_event:
                    prefix = "СОБЫТИЕ: "
                elif mem.is_action_result:
                    prefix = "РЕЗУЛЬТАТ: "
                display = self._get_registry().get_name(mem.speaker_id) if mem.speaker_id else mem.speaker
                context_parts.append(f"  [тик {mem.tick}] {prefix}[{display}]: {mem.text}")
            context_parts.append("")

        # Релевантные воспоминания из векторной БД
        try:
            recent_texts = [m.text for m in self.short_term[-5:]]
            current_event = ""
            for m in reversed(self.short_term):
                if m.is_event:
                    current_event = m.text
                    break
            exclude_ticks = {m.tick for m in self.short_term[-10:]}
            vector_results = self.vector_layer.search_by_context(
                recent_texts, current_event=current_event,
                exclude_ticks=exclude_ticks,
            )
            if vector_results:
                context_parts.append("=== СВЯЗАННЫЕ ВОСПОМИНАНИЯ ===")
                for vdoc in vector_results:
                    prefix = "[Событие] " if vdoc.is_event else ""
                    display = self._get_registry().get_name(vdoc.speaker_id) if vdoc.speaker_id else vdoc.speaker
                    context_parts.append(f"  [тик {vdoc.tick}] {prefix}[{display}]: {vdoc.text[:120]}")
                context_parts.append("")
        except Exception:
            pass  # векторный поиск не критичен — основная память работает

        if self.completed_actions:
            context_parts.append("═══ ТЫ УЖЕ ДЕЛАЛ ЭТО (НЕ ПОВТОРЯЙ!) ═══")
            for action in self.completed_actions[-8:]:
                context_parts.append(f"  * {action}")
            context_parts.append("Придумай НОВОЕ действие!\n")

        return "\n".join(context_parts) if context_parts else ""

    def save_to_db(self):
        chroma_storage.save_agent_memories(
            agent_id=self.agent_id,
            short_term=[m.to_dict() for m in self.short_term],
            long_term=[m.to_dict() for m in self.long_term],
            completed_actions=self.completed_actions,
            group_decisions=self.group_decisions,
            user_id=self.user_id,
        )
        try:
            self.vector_layer.save()
        except Exception:
            pass

    def load_from_db(self):
        try:
            data = chroma_storage.load_agent_memories(self.agent_id, user_id=self.user_id)
            _removed_fields = {'openness', 'conscientiousness', 'extraversion',
                               'agreeableness', 'neuroticism', 'talkativeness'}
            def _clean(item: dict) -> dict:
                return {k: v for k, v in item.items() if k not in _removed_fields}
            self.short_term = [MemoryItem(**_clean(item)) for item in data.get("short_term", [])]
            self.long_term = [MemoryItem(**_clean(item)) for item in data.get("long_term", [])]
            self.completed_actions = data.get("completed_actions", [])
            self.group_decisions = data.get("group_decisions", [])
        except Exception as e:
            print(f"{Fore.YELLOW}Не удалось загрузить память для {self.agent_id}: {e}{Style.RESET_ALL}")
