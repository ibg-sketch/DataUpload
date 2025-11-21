"""
OpenAI API client with retry, timeout, rate limiting, and caching
Uses raw HTTP requests to guarantee UTF-8 encoding
VERSION: 2.0 - All logger.debug removed to fix Unicode encoding issue
"""

import os
import time
import json
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self, config: Dict[str, Any]):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.timeout = config.get('timeout_sec', 20)
        self.max_retries = config.get('max_retries', 2)
        
        self.max_calls_per_hour = config.get('max_calls_per_hour', 60)
        self.max_tokens_per_day = config.get('max_tokens_per_day', 200000)
        
        self.cache = {}
        self.cache_ttl = 1800
        
        self.call_history = []
        self.token_history = []
        
        self.api_url = "https://api.openai.com/v1/chat/completions"
        
        logger.info(f"AIClient initialized with model={self.model}, timeout={self.timeout}s, using raw HTTP")
    
    def _get_cache_key(self, system_prompt: str, user_prompt: str) -> str:
        """Generate cache key from prompts"""
        combined = f"{system_prompt}|{user_prompt}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
    
    def _check_cache(self, cache_key: str) -> Optional[str]:
        """Check if response is cached and still valid"""
        if cache_key in self.cache:
            cached_time, cached_response = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.info(f"Cache hit for key={cache_key[:8]}")
                return cached_response
            else:
                del self.cache[cache_key]
        return None
    
    def _update_cache(self, cache_key: str, response: str):
        """Update cache with new response"""
        self.cache[cache_key] = (time.time(), response)
        
        if len(self.cache) > 100:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][0])
            del self.cache[oldest_key]
    
    def _check_rate_limits(self) -> bool:
        """Check if rate limits are exceeded"""
        now = time.time()
        
        hour_ago = now - 3600
        self.call_history = [t for t in self.call_history if t > hour_ago]
        
        if len(self.call_history) >= self.max_calls_per_hour:
            logger.warning(f"Rate limit exceeded: {len(self.call_history)} calls in last hour")
            return False
        
        day_ago = now - 86400
        self.token_history = [(t, tokens) for t, tokens in self.token_history if t > day_ago]
        
        total_tokens = sum(tokens for _, tokens in self.token_history)
        if total_tokens >= self.max_tokens_per_day:
            logger.warning(f"Token limit exceeded: {total_tokens} tokens in last day")
            return False
        
        return True
    
    def _record_usage(self, tokens_used: int):
        """Record API call and token usage"""
        now = time.time()
        self.call_history.append(now)
        self.token_history.append((now, tokens_used))
    
    
    def get_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get completion from OpenAI with retry and rate limiting
        
        Returns:
            {
                'response': str,
                'tokens_in': int,
                'tokens_out': int,
                'cost_usd': float,
                'cached': bool,
                'error': str or None
            }
        """
        cache_key = self._get_cache_key(system_prompt, user_prompt)
        
        if use_cache:
            cached = self._check_cache(cache_key)
            if cached:
                return {
                    'response': cached,
                    'tokens_in': 0,
                    'tokens_out': 0,
                    'cost_usd': 0.0,
                    'cached': True,
                    'error': None
                }
        
        if not self._check_rate_limits():
            return {
                'response': None,
                'tokens_in': 0,
                'tokens_out': 0,
                'cost_usd': 0.0,
                'cached': False,
                'error': 'Rate limit exceeded'
            }
        
        for attempt in range(self.max_retries + 1):
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json; charset=utf-8"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.7
                }
                
                payload_json = json.dumps(payload, ensure_ascii=False).encode('utf-8')
                
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    data=payload_json,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                
                result = response.json()
                
                content = result['choices'][0]['message']['content'].strip()
                tokens_in = result['usage']['prompt_tokens']
                tokens_out = result['usage']['completion_tokens']
                total_tokens = tokens_in + tokens_out
                
                if 'gpt-4o-mini' in self.model:
                    cost_usd = (tokens_in * 0.00015 + tokens_out * 0.0006) / 1000
                elif 'gpt-4o' in self.model:
                    cost_usd = (tokens_in * 0.0025 + tokens_out * 0.01) / 1000
                else:
                    cost_usd = (tokens_in * 0.0005 + tokens_out * 0.0015) / 1000
                
                self._record_usage(total_tokens)
                
                if use_cache:
                    self._update_cache(cache_key, content)
                
                logger.info(f"API call successful: {tokens_in}+{tokens_out} tokens, ${cost_usd:.4f}")
                
                return {
                    'response': content,
                    'tokens_in': tokens_in,
                    'tokens_out': tokens_out,
                    'cost_usd': cost_usd,
                    'cached': False,
                    'error': None
                }
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"API call failed (attempt {attempt + 1}/{self.max_retries + 1}): {error_msg}")
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    return {
                        'response': None,
                        'tokens_in': 0,
                        'tokens_out': 0,
                        'cost_usd': 0.0,
                        'cached': False,
                        'error': error_msg
                    }
        
        return {
            'response': None,
            'tokens_in': 0,
            'tokens_out': 0,
            'cost_usd': 0.0,
            'cached': False,
            'error': 'Max retries exceeded'
        }
    
    def parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse AI response to extract ai_confidence, TTL, target, and reasoning
        
        Expected format:
        {
          "ai_confidence": 75,
          "ai_ttl_minutes": 25,
          "ai_target_pct": 0.8,
          "reasoning": "Strong bearish setup..."
        }
        
        Returns:
            {
                'ai_confidence': int (0-100) or None,
                'ai_ttl_minutes': int (10-45) or None,
                'ai_target_pct': float (0.2-2.0) or None,
                'reasoning': str or None,
                'parse_error': str or None
            }
        """
        if not response_text:
            return {
                'ai_confidence': None,
                'ai_ttl_minutes': None,
                'ai_target_pct': None,
                'reasoning': None,
                'parse_error': 'Empty response'
            }
        
        try:
            response_text = response_text.strip()
            
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            data = json.loads(response_text)
            
            ai_confidence = data.get('ai_confidence')
            ai_ttl_minutes = data.get('ai_ttl_minutes')
            ai_target_pct = data.get('ai_target_pct')
            reasoning = data.get('reasoning', '')
            
            if ai_confidence is None:
                return {
                    'ai_confidence': None,
                    'ai_ttl_minutes': ai_ttl_minutes,
                    'ai_target_pct': ai_target_pct,
                    'reasoning': reasoning,
                    'parse_error': 'Missing ai_confidence field'
                }
            
            ai_confidence = int(ai_confidence)
            if not (0 <= ai_confidence <= 100):
                logger.warning(f"AI confidence out of range: {ai_confidence}, clamping to 0-100")
                ai_confidence = max(0, min(100, ai_confidence))
            
            if ai_ttl_minutes is not None:
                ai_ttl_minutes = int(ai_ttl_minutes)
                if not (10 <= ai_ttl_minutes <= 45):
                    logger.warning(f"AI TTL out of range: {ai_ttl_minutes}, clamping to 10-45")
                    ai_ttl_minutes = max(10, min(45, ai_ttl_minutes))
            
            if ai_target_pct is not None:
                ai_target_pct = float(ai_target_pct)
                if not (0.2 <= ai_target_pct <= 2.0):
                    logger.warning(f"AI target out of range: {ai_target_pct}, clamping to 0.2-2.0")
                    ai_target_pct = max(0.2, min(2.0, ai_target_pct))
            
            return {
                'ai_confidence': ai_confidence,
                'ai_ttl_minutes': ai_ttl_minutes,
                'ai_target_pct': ai_target_pct,
                'reasoning': reasoning[:500],
                'parse_error': None
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}, response: {response_text[:200]}")
            return {
                'ai_confidence': None,
                'ai_ttl_minutes': None,
                'ai_target_pct': None,
                'reasoning': response_text[:500],
                'parse_error': f'JSON decode error: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected parse error: {e}")
            return {
                'ai_confidence': None,
                'ai_ttl_minutes': None,
                'ai_target_pct': None,
                'reasoning': response_text[:500] if response_text else None,
                'parse_error': str(e)
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current usage statistics"""
        now = time.time()
        
        hour_ago = now - 3600
        calls_hour = len([t for t in self.call_history if t > hour_ago])
        
        day_ago = now - 86400
        tokens_day = sum(tokens for t, tokens in self.token_history if t > day_ago)
        
        return {
            'calls_hour': calls_hour,
            'calls_limit': self.max_calls_per_hour,
            'tokens_day': tokens_day,
            'tokens_limit': self.max_tokens_per_day,
            'cache_size': len(self.cache)
        }
