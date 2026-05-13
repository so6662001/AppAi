import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { BriefingFeed, BriefingCard } from '@/types/briefing';
import { briefingApi, fakeFeed } from '@/services/briefing';

export const useBriefingStore = defineStore('briefing', () => {
  const feed = ref<BriefingFeed | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const readIds = ref<Set<number>>(new Set());

  async function loadToday(date?: string) {
    loading.value = true;
    error.value = null;
    try {
      feed.value = await briefingApi.today(date);
    } catch (e: any) {
      // 后端不可达, 用演示数据展示 UI
      feed.value = fakeFeed();
      error.value = '后端未连接, 显示演示数据';
    } finally {
      loading.value = false;
    }
  }

  async function refresh() { await loadToday(); }

  async function markRead(card_id: number) {
    if (readIds.value.has(card_id)) return;
    readIds.value.add(card_id);
    try { await briefingApi.markRead(card_id); } catch {}
  }

  async function ignore(card_id: number) {
    if (!feed.value) return;
    feed.value.cards = feed.value.cards.filter(c => c.card_id !== card_id);
    try { await briefingApi.ignore(card_id); } catch {}
  }

  async function feedback(card_id: number, vote: 'UP' | 'DOWN', reason?: string) {
    try { await briefingApi.feedback(card_id, { vote, reason }); } catch {}
  }

  function findCard(card_id: number): BriefingCard | undefined {
    return feed.value?.cards.find(c => c.card_id === card_id);
  }

  return { feed, loading, error, readIds, loadToday, refresh, markRead, ignore, feedback, findCard };
});
