import json
import re
import requests
from config import setup_global_proxy

# ==========================================
# Phase 3: Decision Layer (DeepSeek Brain Integration)
# ==========================================

# 预设 API KEY (请替换为您真实的 DeepSeek API Key)
# Preset API KEY (Please replace with your actual DeepSeek API Key)
DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
# 假设我们使用的是 r1 推理模型
# Assuming we are using the r1 reasoning model
MODEL_NAME = "deepseek-reasoner" 

def build_system_prompt() -> str:
    """
    构建严格的系统级提示词 (System-level Prompt)
    """
    return """You are a battle-tested quantitative trading AI.
Your objective is to analyze the provided HK stock data (price-volume and news sentiment) and make a discrete trading decision.

STRICT OUTPUT RULES:
1. You MUST output ONLY a valid JSON object.
2. No markdown formatting, no conversational text before or after the JSON.
3. The JSON must exactly match this structure:
{
    "action": "BUY" | "SELL" | "HOLD",
    "reason": "A concise, 1-2 sentence explanation of your rationale"
}
"""

def clean_r1_output(raw_output: str) -> str:
    """
    针对 DeepSeek-R1 模型的特殊解析：剥离 <think> 标签及其内容。
    Specific parsing for DeepSeek-R1: Strip <think> tags and their contents.
    
    :param raw_output: 大模型返回的原始字符串
    :return: 清洗后的纯 JSON 字符串
    """
    # 1. 使用 Regex 剔除 <think>...</think> 块（包括跨行）
    # Use Regex to remove <think>...</think> blocks (including multiline)
    cleaned = re.sub(r'<think>.*?</think>', '', raw_output, flags=re.DOTALL)
    
    # 2. 如果包含 markdown 的 ```json 代码块，定向提取出来
    # If it contains markdown ```json blocks, extract the core content
    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', cleaned, flags=re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # 3. 兜底清理首尾空白符
    return cleaned.strip()

def ask_deepseek(symbol: str, market_data: dict, news_list: list, retry_count: int = 3) -> dict:
    """
    与 DeepSeek 大脑进行交互并带有容错回退机制
    Interact with the DeepSeek Brain with fault-tolerance and fallback mechanisms.
    """
    system_prompt = build_system_prompt()
    user_prompt = f"""
TARGET ASSET: {symbol}
MARKET DATA SNAPSHOT (Last 60 mins):
{json.dumps(market_data, ensure_ascii=False, indent=2)}

LATEST NEWS/SENTIMENT:
{json.dumps(news_list, ensure_ascii=False, indent=2)}

Based strictly on this data, provide your JSON decision.
"""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1 # 降低温度，减少幻觉 (Lower temperature to reduce hallucinations)
    }

    print(f"[*] 正在向 DeepSeek 云端大脑发送 {symbol} 的决策请求...")

    for attempt in range(1, retry_count + 1):
        try:
            # 发送请求 (发送到底层 Requests 时会自动走 config.py 中挂载的代理)
            # Send request (will automatically use the proxy mounted in config.py)
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            # 提取大模型的原始回复
            raw_content = response.json()['choices'][0]['message']['content']
            
            # 使用针对 R1 的清洗机制
            # Use R1-specific cleaning mechanism
            pure_json_str = clean_r1_output(raw_content)
            
            # 强类型/严格解析
            # Strict Parsing
            decision = json.loads(pure_json_str)
            
            # 校验字段
            if "action" not in decision or decision["action"] not in ["BUY", "SELL", "HOLD"]:
                raise ValueError("JSON 缺少 action 字段或内容不合法")
                
            print(f"[+] 决策成功解析: {decision['action']} (Attempt {attempt})")
            return decision

        except Exception as e:
            print(f"[-] 尝试 {attempt}/{retry_count} 失败: {str(e)}")
            if attempt == retry_count:
                # 触发回退逻辑防线 (Trigger fallback logic defense)
                print(f"[!] 警告: 达到最大重试次数，触发默认防崩溃回退逻辑 (HOLD)！")
                return {"action": "HOLD", "reason": f"API_ERROR_OR_PARSE_FAILED: {str(e)}"}

if __name__ == "__main__":
    setup_global_proxy()
    # 模拟沙盒测试数据 (Mock Sandbox Data)
    mock_market = {"close": 280.5, "RSI_14": 35.2, "MACD": -1.5}
    mock_news = ["腾讯大模型取得突破", "游戏业务超预期"]
    
    # 这个调用会因为没有真实的 API Key 而返回 401 错误，但能验证 Fallback 机制是否有效触发
    # This call will fail with 401 due to a dummy API key, which perfectly verifies the Fallback mechanism.
    decision = ask_deepseek("00700", mock_market, mock_news)
    print("最终输出 (Final Output):", decision)
