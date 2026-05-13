import type { CardAction } from '@/types/briefing';

export function useActions() {

  async function run(card_id: number, action: CardAction) {
    // 二次确认
    if (action.confirm) {
      const ok = await new Promise<boolean>((resolve) => {
        uni.showModal({
          title: action.confirm!.title,
          content: action.confirm!.message,
          success: (r) => resolve(r.confirm),
        });
      });
      if (!ok) return;
    }

    switch (action.type) {
      case 'chat': {
        const dsl = action.dsl ? encodeURIComponent(JSON.stringify(action.dsl)) : '';
        uni.navigateTo({ url: `/pages/ai/chat?card_id=${card_id}&prefillDsl=${dsl}` });
        break;
      }
      case 'navigate': {
        if (!action.path) return;
        uni.navigateTo({ url: action.path });
        break;
      }
      case 'action': {
        // 通用业务接口调用
        uni.showLoading({ title: '处理中…' });
        try {
          // 真实环境调用对应 handler 的接口
          await new Promise((r) => setTimeout(r, 600));
          uni.hideLoading();
          uni.showToast({ title: '已执行', icon: 'success' });
        } catch (e) {
          uni.hideLoading();
          uni.showToast({ title: '执行失败', icon: 'error' });
        }
        break;
      }
    }
  }

  return { run };
}
