# core/tools/session/analyzer.py
from typing import List, Dict
from core.models.session import SessionState, ImportantInfo

class SessionAnalyzer:
    """会话分析工具"""
    
    @staticmethod
    def get_relevant_info(session: SessionState, 
                         current_message: str,
                         max_items: int = 3) -> List[ImportantInfo]:
        """获取与当前消息相关的重要信息"""
        # 简单的相关性评分
        def calculate_relevance(info: ImportantInfo) -> float:
            relevance = 0.0
            # 检查类别相关性
            if any(keyword in current_message.lower() for keyword in info.category.split('_')):
                relevance += 0.5
            # 检查内容相关性
            if any(word in current_message.lower() for word in info.content.lower().split()):
                relevance += 0.3
            # 考虑信息的确信度
            relevance *= info.confidence
            return relevance

        # 为每条信息计算相关性分数
        scored_info = [
            (info, calculate_relevance(info))
            for info in session.important_info
        ]
        
        # 按相关性排序并返回最相关的信息
        return [
            info for info, score in sorted(scored_info, key=lambda x: x[1], reverse=True)
            if score > 0.3  # 只返回相关性超过阈值的信息
        ][:max_items]

    @staticmethod
    def get_theme_suggestions(session: SessionState) -> List[str]:
        """基于历史信息推荐主题"""
        themes = []
        
        # 从重要信息中提取主题相关的信息
        theme_info = [
            info for info in session.important_info
            if info.category == 'theme'
        ]
        
        # 从对话历史中提取关键词
        keywords = set()
        for msg in session.conversation_history:
            if msg['role'] == 'user':
                # 简单的关键词提取
                words = msg['content'].lower().split()
                keywords.update(
                    word for word in words
                    if len(word) > 3 and word not in {'what', 'when', 'where', 'build', 'make'}
                )
        
        # 组合推荐主题
        if theme_info:
            themes.extend(info.content for info in theme_info)
        if keywords:
            themes.extend(list(keywords)[:3])
        
        return list(set(themes))

    @staticmethod
    def summarize_session(session: SessionState) -> Dict:
        """生成会话摘要"""
        return {
            'current_theme': session.current_theme,
            'preferences': [
                info.content
                for info in session.important_info
                if info.category == 'preference'
            ],
            'goals': [
                info.content
                for info in session.important_info
                if info.category == 'goal'
            ],
            'message_count': len(session.conversation_history),
            'last_active': session.last_active
        }