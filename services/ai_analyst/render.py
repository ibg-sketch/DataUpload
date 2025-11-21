"""
Format AI responses for Telegram output
"""

import logging

logger = logging.getLogger(__name__)


class ResponseRenderer:
    """Format AI responses for different output contexts"""
    
    @staticmethod
    def render_market_context(
        bot_confidence: float,
        ai_confidence: int = None,
        ai_ttl_minutes: int = None,
        ai_target_pct: float = None,
        bot_ttl_minutes: int = None,
        bot_target_pct: float = None,
        reasoning: str = None,
        max_chars: int = 500
    ) -> str:
        """
        Format per-signal market context for Telegram
        
        Args:
            bot_confidence: Bot's calculated confidence (0-1 decimal format)
            ai_confidence: AI's independent confidence (0-100) or None
            ai_ttl_minutes: AI's recommended TTL in minutes or None
            ai_target_pct: AI's recommended target profit % or None
            bot_ttl_minutes: Bot's calculated TTL in minutes or None
            bot_target_pct: Bot's calculated target profit % or None
            reasoning: AI's reasoning text or None
            max_chars: Maximum character limit for reasoning
        
        Returns:
            Formatted string ready for Telegram HTML
        """
        if not reasoning and ai_confidence is None:
            return ""
        
        lines = []
        
        if ai_confidence is not None:
            lines.append(f"🤖 <b>AI Assessment: {ai_confidence}% confidence</b>")
            
            if bot_confidence is not None:
                logger.info(f"[DEBUG] bot_confidence raw value: {bot_confidence} (type: {type(bot_confidence)})")
                bot_conf_pct = bot_confidence * 100
                logger.info(f"[DEBUG] bot_conf_pct after *100: {bot_conf_pct:.2f}")
                diff = ai_confidence - bot_conf_pct
                if abs(diff) <= 10:
                    agreement = "✅ Agrees"
                elif diff > 10:
                    agreement = "⬆️ More confident"
                else:
                    agreement = "⬇️ Less confident"
                lines.append(f"   {agreement} (Bot: {bot_conf_pct:.0f}%)")
        else:
            lines.append("🤖 <b>AI Analysis:</b>")
        
        params_line = []
        if ai_ttl_minutes is not None:
            if bot_ttl_minutes is not None:
                ttl_diff = ai_ttl_minutes - bot_ttl_minutes
                ttl_indicator = "📍" if abs(ttl_diff) <= 5 else ("⏱️" if ttl_diff < 0 else "⏳")
                params_line.append(f"{ttl_indicator} TTL: {ai_ttl_minutes}min (bot: {bot_ttl_minutes}min)")
            else:
                params_line.append(f"⏱️ TTL: {ai_ttl_minutes}min")
        
        if ai_target_pct is not None:
            if bot_target_pct is not None:
                target_diff = abs(ai_target_pct - bot_target_pct)
                target_indicator = "🎯" if target_diff <= 0.2 else ("🔻" if ai_target_pct < bot_target_pct else "🔺")
                params_line.append(f"{target_indicator} Target: {ai_target_pct:.1f}% (bot: {bot_target_pct:.1f}%)")
            else:
                params_line.append(f"🎯 Target: {ai_target_pct:.1f}%")
        
        if params_line:
            lines.append(f"   {' | '.join(params_line)}")
        
        if reasoning:
            cleaned = reasoning.strip()
            
            if len(cleaned) > max_chars:
                cleaned = cleaned[:max_chars - 3] + "..."
                logger.warning(f"Reasoning truncated to {max_chars} chars")
            
            reason_lines = cleaned.split('\n')
            reason_lines = [line.strip() for line in reason_lines if line.strip()]
            formatted_reasoning = ' '.join(reason_lines)
            
            if not formatted_reasoning.endswith(('.', '!', '?')):
                formatted_reasoning += '.'
            
            lines.append(f"<i>{formatted_reasoning}</i>")
        
        return '\n'.join(lines)
    
    @staticmethod
    def render_daily_summary(ai_response: str, date_str: str) -> str:
        """
        Format daily summary for Telegram
        
        Args:
            ai_response: Raw AI response (markdown format)
            date_str: Date string (YYYY-MM-DD)
        
        Returns:
            Formatted string ready for Telegram HTML
        """
        if not ai_response:
            return ""
        
        lines = ai_response.strip().split('\n')
        html_lines = []
        
        html_lines.append(f"<b>📊 AI Daily Summary - {date_str}</b>\n")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('# '):
                html_lines.append(f"<b>{line[2:]}</b>")
            elif line.startswith('## '):
                html_lines.append(f"\n<b>{line[3:]}</b>")
            elif line.startswith('### '):
                html_lines.append(f"\n<i>{line[4:]}</i>")
            elif line.startswith('- ') or line.startswith('* '):
                html_lines.append(f"  • {line[2:]}")
            elif line.startswith('**') and line.endswith('**'):
                html_lines.append(f"<b>{line[2:-2]}</b>")
            else:
                html_lines.append(line)
        
        return '\n'.join(html_lines)
    
    @staticmethod
    def truncate_summary(text: str, max_length: int = 100) -> str:
        """
        Create truncated summary for CSV logging
        
        Args:
            text: Full text
            max_length: Maximum length in words
        
        Returns:
            Truncated summary
        """
        words = text.split()
        if len(words) <= max_length:
            return text
        
        truncated = ' '.join(words[:max_length]) + '...'
        return truncated
