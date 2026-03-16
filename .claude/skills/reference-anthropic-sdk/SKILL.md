---
name: reference-anthropic-sdk
description: "Anthropic Python/TypeScript Client SDK 및 Claude Agent SDK 레퍼런스. 설치, 클라이언트 초기화, Messages API, 스트리밍, Tool Use, 에러 처리, Agent SDK(query, ClaudeAgentOptions, 도구, 훅, 서브에이전트, 세션, MCP)의 코드 예시와 공식문서 링크를 제공한다. Use when: Anthropic SDK 설치법·API 사용법을 확인할 때, Agent SDK로 에이전트를 구현할 때, 스트리밍·Tool Use·에러 처리 패턴을 참조할 때"
license: "Apache-2.0"
---

# Anthropic SDK & Claude Agent SDK 레퍼런스

Anthropic Python/TypeScript Client SDK와 Claude Agent SDK의 핵심 레퍼런스. 코드 예시와 공식문서 링크를 제공한다.

공식문서:
- Client SDK 개요: https://platform.claude.com/docs/en/api/client-sdks
- Python SDK: https://platform.claude.com/docs/en/api/sdks/python
- TypeScript SDK: https://platform.claude.com/docs/en/api/sdks/typescript
- Agent SDK 개요: https://platform.claude.com/docs/en/agent-sdk/overview
- Agent SDK Quickstart: https://platform.claude.com/docs/en/agent-sdk/quickstart
- GitHub(Python SDK): https://github.com/anthropics/anthropic-sdk-python
- GitHub(TypeScript SDK): https://github.com/anthropics/anthropic-sdk-typescript
- GitHub(Agent SDK Python): https://github.com/anthropics/claude-agent-sdk-python
- GitHub(Agent SDK TypeScript): https://github.com/anthropics/claude-agent-sdk-typescript

---

## 1. Anthropic Client SDK

Claude API에 직접 접근하는 SDK. 메시지 요청/응답, 스트리밍, Tool Use를 구현해야 할 때 사용한다.

### 1-1. Python SDK

**설치:**
```bash
pip install anthropic

# 플랫폼 통합 추가 옵션
pip install anthropic[bedrock]   # AWS Bedrock
pip install anthropic[vertex]    # Google Vertex AI
pip install anthropic[aiohttp]   # aiohttp 백엔드(비동기 성능 향상)
```

**요구사항:** Python 3.9+

**기본 사용:**
```python
import os
from anthropic import Anthropic

client = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),  # 기본값: 환경변수에서 자동 로드
)

message = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello, Claude"}],
)
print(message.content)
```

**비동기(Async) 사용:**
```python
import asyncio
from anthropic import AsyncAnthropic

client = AsyncAnthropic()

async def main():
    message = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )
    print(message.content)

asyncio.run(main())
```

**스트리밍 - 기본(stream=True):**
```python
stream = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello, Claude"}],
    stream=True,
)
for event in stream:
    print(event.type)
```

**스트리밍 - 헬퍼(messages.stream):**
```python
async with client.messages.stream(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Say hello!"}],
) as stream:
    async for text in stream.text_stream:
        print(text, end="", flush=True)
    message = await stream.get_final_message()
```

**Tool Use + beta_tool 헬퍼:**
```python
import json
from anthropic import Anthropic, beta_tool

client = Anthropic()

@beta_tool
def get_weather(location: str) -> str:
    """Get the weather for a given location.

    Args:
        location: The city and state, e.g. San Francisco, CA
    Returns:
        A dictionary containing the location, temperature, and weather condition.
    """
    return json.dumps({"location": location, "temperature": "68°F", "condition": "Sunny"})

runner = client.beta.messages.tool_runner(
    model="claude-opus-4-6",
    max_tokens=1024,
    tools=[get_weather],
    messages=[{"role": "user", "content": "What is the weather in SF?"}],
)
for message in runner:
    print(message)
```

**에러 처리:**
```python
import anthropic

try:
    message = client.messages.create(...)
except anthropic.APIConnectionError as e:
    print("서버에 연결할 수 없음:", e.__cause__)
except anthropic.RateLimitError as e:
    print("429 Rate Limit:", e)
except anthropic.APIStatusError as e:
    print(f"API 오류 {e.status_code}:", e.response)
```

에러 코드 테이블:

| 상태 코드 | 예외 클래스 |
|----------|------------|
| 400 | `BadRequestError` |
| 401 | `AuthenticationError` |
| 403 | `PermissionDeniedError` |
| 404 | `NotFoundError` |
| 422 | `UnprocessableEntityError` |
| 429 | `RateLimitError` |
| >=500 | `InternalServerError` |
| N/A | `APIConnectionError` |

**재시도 & 타임아웃:**
```python
# 재시도: 기본 2회(Connection, 408, 409, 429, >=500 자동 재시도)
client = Anthropic(max_retries=0)  # 재시도 비활성화

# 타임아웃: 기본 10분
import httpx
client = Anthropic(timeout=httpx.Timeout(60.0, read=5.0, write=10.0, connect=2.0))

# 요청별 오버라이드
client.with_options(max_retries=5).messages.create(...)
client.with_options(timeout=5.0).messages.create(...)
```

**토큰 카운팅:**
```python
# 응답 후 usage 확인
message = client.messages.create(...)
print(message.usage)  # Usage(input_tokens=25, output_tokens=13)

# 요청 전 카운팅
count = client.messages.count_tokens(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "Hello, world"}]
)
print(count.input_tokens)  # 10
```

**플랫폼 통합 클라이언트:**
```python
from anthropic import AnthropicBedrock  # pip install anthropic[bedrock]
from anthropic import AnthropicVertex   # pip install anthropic[vertex]
from anthropic import AnthropicFoundry  # 추가 패키지 불필요
```

**디버깅:**
```bash
export ANTHROPIC_LOG=debug  # debug | info | warn | off
```

---

### 1-2. TypeScript SDK

**설치:**
```bash
npm install @anthropic-ai/sdk
```

**요구사항:** TypeScript 4.9+, Node.js 20+, Deno 1.28+, Bun 1.0+, Cloudflare Workers 지원

**기본 사용:**
```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: process.env["ANTHROPIC_API_KEY"], // 기본값: 환경변수에서 자동 로드
});

const message = await client.messages.create({
  model: "claude-opus-4-6",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello, Claude" }],
});
console.log(message.content);
```

**TypeScript 타입 사용:**
```typescript
const params: Anthropic.MessageCreateParams = {
  model: "claude-opus-4-6",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello, Claude" }],
};
const message: Anthropic.Message = await client.messages.create(params);
```

**스트리밍 - 기본(stream: true):**
```typescript
const stream = await client.messages.create({
  model: "claude-opus-4-6",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello, Claude" }],
  stream: true,
});
for await (const event of stream) {
  console.log(event.type);
}
// 스트림 취소: stream.controller.abort() 또는 break
```

**스트리밍 - 헬퍼(messages.stream):**
```typescript
const stream = anthropic.messages
  .stream({
    model: "claude-opus-4-6",
    max_tokens: 1024,
    messages: [{ role: "user", content: "Say hello!" }],
  })
  .on("text", (text) => console.log(text));

const message = await stream.finalMessage();
```

**Tool Use - Zod 헬퍼:**
```typescript
import { betaZodTool } from "@anthropic-ai/sdk/helpers/beta/zod";
import { z } from "zod";

const weatherTool = betaZodTool({
  name: "get_weather",
  inputSchema: z.object({ location: z.string() }),
  description: "Get the current weather in a given location",
  run: (input) => `The weather in ${input.location} is foggy and 60°F`,
});

const finalMessage = await anthropic.beta.messages.toolRunner({
  model: "claude-opus-4-6",
  max_tokens: 1000,
  messages: [{ role: "user", content: "What is the weather in SF?" }],
  tools: [weatherTool],
});
```

**에러 처리:**
```typescript
await client.messages
  .create({ model: "claude-opus-4-6", max_tokens: 1024, messages: [...] })
  .catch((err) => {
    if (err instanceof Anthropic.APIError) {
      console.log(err.status);   // 400
      console.log(err.name);     // BadRequestError
      console.log(err.headers);
    }
  });
```

에러 코드 테이블:

| 상태 코드 | 예외 클래스 |
|----------|------------|
| 400 | `BadRequestError` |
| 401 | `AuthenticationError` |
| 403 | `PermissionDeniedError` |
| 404 | `NotFoundError` |
| 422 | `UnprocessableEntityError` |
| 429 | `RateLimitError` |
| >=500 | `InternalServerError` |
| N/A | `APIConnectionError` |

**재시도 & 타임아웃:**
```typescript
// 재시도 설정
const client = new Anthropic({ maxRetries: 0 }); // 기본 2회

// 타임아웃 설정 (기본 10분)
const client = new Anthropic({ timeout: 20 * 1000 }); // 20초

// 요청별 오버라이드
await client.messages.create({ ... }, { maxRetries: 5, timeout: 5000 });
```

**플랫폼 통합 패키지:**
```bash
npm install @anthropic-ai/bedrock-sdk   # AnthropicBedrock 클라이언트
npm install @anthropic-ai/vertex-sdk    # AnthropicVertex 클라이언트
npm install @anthropic-ai/foundry-sdk   # AnthropicFoundry 클라이언트
```

**브라우저 지원:**
```typescript
const client = new Anthropic({
  dangerouslyAllowBrowser: true,  // 경고: API 키가 클라이언트에 노출됨
});
```

**로깅:**
```typescript
const client = new Anthropic({ logLevel: "debug" }); // debug | info | warn | error | off
```

---

## 2. Claude Agent SDK

Claude Code의 도구·에이전트 루프를 프로그래밍 방식으로 사용하는 SDK. 자율 에이전트를 구축할 때 사용한다. Client SDK와 달리 Tool 실행을 SDK가 자동으로 처리한다.

> **주의:** Claude Code SDK가 Claude Agent SDK로 이름 변경됨. 마이그레이션: https://platform.claude.com/docs/en/agent-sdk/migration-guide

### 2-1. 설치

**Python:**
```bash
pip install claude-agent-sdk
```

**TypeScript:**
```bash
npm install @anthropic-ai/claude-agent-sdk
```

**인증:**
```bash
export ANTHROPIC_API_KEY=your-api-key

# 서드파티 플랫폼
export CLAUDE_CODE_USE_BEDROCK=1   # AWS Bedrock
export CLAUDE_CODE_USE_VERTEX=1    # Google Vertex AI
export CLAUDE_CODE_USE_FOUNDRY=1   # Microsoft Azure
```

### 2-2. query() - 핵심 API

에이전트 루프를 시작하는 메인 진입점. 비동기 이터레이터로 메시지를 스트리밍한다.

**Python:**
```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

async def main():
    async for message in query(
        prompt="Find and fix the bug in auth.py",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Bash"],
            permission_mode="acceptEdits",
        ),
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text"):
                    print(block.text)
                elif hasattr(block, "name"):
                    print(f"Tool: {block.name}")
        elif isinstance(message, ResultMessage):
            print(f"Done: {message.subtype}")

asyncio.run(main())
```

**TypeScript:**
```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Find and fix the bug in auth.py",
  options: {
    allowedTools: ["Read", "Edit", "Bash"],
    permissionMode: "acceptEdits",
  },
})) {
  if (message.type === "assistant" && message.message?.content) {
    for (const block of message.message.content) {
      if ("text" in block) console.log(block.text);
      else if ("name" in block) console.log(`Tool: ${block.name}`);
    }
  } else if (message.type === "result") {
    console.log(`Done: ${message.subtype}`);
  }
}
```

### 2-3. ClaudeAgentOptions 옵션 레퍼런스

Python(`ClaudeAgentOptions`) / TypeScript(options 객체) 주요 파라미터:

| Python 파라미터 | TypeScript 파라미터 | 설명 |
|----------------|---------------------|------|
| `allowed_tools` | `allowedTools` | 사전 승인할 도구 목록 (예: `["Read", "Edit", "Bash"]`) |
| `permission_mode` | `permissionMode` | 권한 모드 (아래 표 참조) |
| `system_prompt` | `systemPrompt` | 에이전트 시스템 프롬프트 |
| `model` | `model` | 사용할 Claude 모델 ID |
| `cwd` | `cwd` | 에이전트 작업 디렉터리 |
| `mcp_servers` | `mcpServers` | MCP 서버 설정 딕셔너리 |
| `agents` | `agents` | 서브에이전트 정의 딕셔너리 |
| `hooks` | `hooks` | 훅 콜백 딕셔너리 |
| `resume` | `resume` | 재개할 세션 ID |
| `setting_sources` | `settingSources` | 설정 소스 (`["project"]` 시 .claude/ 설정 로드) |

**권한 모드(permission_mode):**

| 모드 | 동작 | 용도 |
|------|------|------|
| `acceptEdits` | 파일 편집 자동 승인, 나머지는 요청 | 신뢰된 개발 워크플로우 |
| `dontAsk` (TS only) | `allowedTools` 이외 전부 거부 | 잠긴 헤드리스 에이전트 |
| `bypassPermissions` | 모든 도구 프롬프트 없이 실행 | 샌드박스 CI, 완전 신뢰 환경 |
| `default` | `canUseTool` 콜백으로 개별 승인 | 커스텀 승인 플로우 |

### 2-4. 내장 도구 목록

| 도구 | 기능 |
|------|------|
| `Read` | 작업 디렉터리 내 파일 읽기 |
| `Write` | 새 파일 생성 |
| `Edit` | 기존 파일 정밀 편집 |
| `Bash` | 터미널 명령, 스크립트, git 실행 |
| `Glob` | 패턴으로 파일 탐색 (`**/*.ts`, `src/**/*.py`) |
| `Grep` | 정규식으로 파일 내용 검색 |
| `WebSearch` | 웹 검색 |
| `WebFetch` | 웹 페이지 내용 파싱 |
| `AskUserQuestion` | 사용자에게 선택지 포함 질문 |
| `Agent` | 서브에이전트 호출 |

**도구 조합 패턴:**

| 도구 조합 | 에이전트 능력 |
|----------|-------------|
| `Read, Glob, Grep` | 읽기 전용 분석 |
| `Read, Edit, Glob` | 코드 분석 및 수정 |
| `Read, Edit, Bash, Glob, Grep` | 전체 자동화 |
| `Read, Edit, Bash, ..., Agent` | 서브에이전트 포함 멀티에이전트 |

### 2-5. 훅(Hooks)

에이전트 라이프사이클 핵심 시점에 커스텀 코드를 실행한다.

**사용 가능한 훅 이벤트:** `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `SessionEnd`, `UserPromptSubmit`

**Python 예시 - 파일 변경 감사 로그:**
```python
from datetime import datetime
from claude_agent_sdk import query, ClaudeAgentOptions, HookMatcher

async def log_file_change(input_data, tool_use_id, context):
    file_path = input_data.get("tool_input", {}).get("file_path", "unknown")
    with open("./audit.log", "a") as f:
        f.write(f"{datetime.now()}: modified {file_path}\n")
    return {}

async for message in query(
    prompt="Refactor utils.py",
    options=ClaudeAgentOptions(
        permission_mode="acceptEdits",
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Edit|Write", hooks=[log_file_change])
            ]
        },
    ),
):
    pass
```

**TypeScript 예시:**
```typescript
import { query, HookCallback } from "@anthropic-ai/claude-agent-sdk";
import { appendFile } from "fs/promises";

const logFileChange: HookCallback = async (input) => {
  const filePath = (input as any).tool_input?.file_path ?? "unknown";
  await appendFile("./audit.log", `${new Date().toISOString()}: modified ${filePath}\n`);
  return {};
};

for await (const message of query({
  prompt: "Refactor utils.py",
  options: {
    permissionMode: "acceptEdits",
    hooks: {
      PostToolUse: [{ matcher: "Edit|Write", hooks: [logFileChange] }],
    },
  },
})) {
  // ...
}
```

훅 상세: https://platform.claude.com/docs/en/agent-sdk/hooks

### 2-6. 서브에이전트(Subagents)

전문화된 에이전트를 정의하여 주 에이전트가 위임할 수 있게 한다. `allowedTools`에 `Agent`를 포함해야 한다.

**Python:**
```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async for message in query(
    prompt="Use the code-reviewer agent to review this codebase",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep", "Agent"],
        agents={
            "code-reviewer": AgentDefinition(
                description="Expert code reviewer for quality and security reviews.",
                prompt="Analyze code quality and suggest improvements.",
                tools=["Read", "Glob", "Grep"],
            )
        },
    ),
):
    pass
```

**TypeScript:**
```typescript
for await (const message of query({
  prompt: "Use the code-reviewer agent to review this codebase",
  options: {
    allowedTools: ["Read", "Glob", "Grep", "Agent"],
    agents: {
      "code-reviewer": {
        description: "Expert code reviewer for quality and security reviews.",
        prompt: "Analyze code quality and suggest improvements.",
        tools: ["Read", "Glob", "Grep"],
      },
    },
  },
})) {
  // ...
}
```

서브에이전트 상세: https://platform.claude.com/docs/en/agent-sdk/subagents

### 2-7. MCP 서버 연동

Model Context Protocol로 외부 시스템(DB, 브라우저, API 등)에 연결한다.

**Python:**
```python
async for message in query(
    prompt="Open example.com and describe what you see",
    options=ClaudeAgentOptions(
        mcp_servers={
            "playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]}
        }
    ),
):
    pass
```

**TypeScript:**
```typescript
for await (const message of query({
  prompt: "Open example.com and describe what you see",
  options: {
    mcpServers: {
      playwright: { command: "npx", args: ["@playwright/mcp@latest"] },
    },
  },
})) {
  // ...
}
```

MCP 상세: https://platform.claude.com/docs/en/agent-sdk/mcp

### 2-8. 세션 관리

멀티턴 에이전트에서 컨텍스트를 유지하거나 이전 세션을 재개한다.

**Python - 세션 캡처 및 재개:**
```python
session_id = None

# 첫 번째 쿼리: 세션 ID 캡처
async for message in query(
    prompt="Read the authentication module",
    options=ClaudeAgentOptions(allowed_tools=["Read", "Glob"]),
):
    if hasattr(message, "subtype") and message.subtype == "init":
        session_id = message.session_id

# 두 번째 쿼리: 세션 재개
async for message in query(
    prompt="Now find all places that call it",
    options=ClaudeAgentOptions(resume=session_id),
):
    if hasattr(message, "result"):
        print(message.result)
```

**TypeScript - 세션 캡처 및 재개:**
```typescript
let sessionId: string | undefined;

for await (const message of query({
  prompt: "Read the authentication module",
  options: { allowedTools: ["Read", "Glob"] },
})) {
  if (message.type === "system" && message.subtype === "init") {
    sessionId = message.session_id;
  }
}

for await (const message of query({
  prompt: "Now find all places that call it",
  options: { resume: sessionId },
})) {
  if ("result" in message) console.log(message.result);
}
```

세션 상세: https://platform.claude.com/docs/en/agent-sdk/sessions

### 2-9. Claude Code 파일시스템 설정 연동

`setting_sources=["project"]` 설정으로 프로젝트의 `.claude/` 설정을 에이전트에서 사용할 수 있다.

| 기능 | 설명 | 위치 |
|------|------|------|
| Skills | Markdown으로 정의된 전문 능력 | `.claude/skills/SKILL.md` |
| Slash commands | 공통 작업용 커스텀 커맨드 | `.claude/commands/*.md` |
| Memory | 프로젝트 컨텍스트 및 지침 | `CLAUDE.md` or `.claude/CLAUDE.md` |
| Plugins | 커스텀 커맨드, 에이전트, MCP 서버 확장 | `plugins` 옵션으로 프로그래밍 방식 |

### 2-10. Client SDK vs Agent SDK 비교

| 구분 | Client SDK | Agent SDK |
|------|-----------|-----------|
| Tool 실행 | 직접 구현 필요 | SDK가 자동 처리 |
| 에이전트 루프 | 직접 구현 | `query()`가 관리 |
| 적합한 용도 | 정밀 제어, 커스텀 Tool | 자율 에이전트, 자동화 |
| 패키지 | `anthropic` | `claude-agent-sdk` / `@anthropic-ai/claude-agent-sdk` |

```python
# Client SDK: Tool 루프를 직접 구현
response = client.messages.create(...)
while response.stop_reason == "tool_use":
    result = your_tool_executor(response.tool_use)
    response = client.messages.create(tool_result=result, **params)

# Agent SDK: SDK가 Tool을 자율적으로 처리
async for message in query(prompt="Fix the bug in auth.py"):
    print(message)
```

---

## 3. 메시지 배치(Message Batches)

대량 요청을 비동기로 처리할 때 사용한다. `client.messages.batches` 네임스페이스.

**Python - 배치 생성:**
```python
client.messages.batches.create(
    requests=[
        {
            "custom_id": "req-1",
            "params": {
                "model": "claude-opus-4-6",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": "Hello, world"}],
            },
        },
        {
            "custom_id": "req-2",
            "params": {
                "model": "claude-opus-4-6",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": "Hi again"}],
            },
        },
    ]
)
```

**Python - 결과 조회(processing_status == 'ended' 이후):**
```python
for entry in client.messages.batches.results(batch_id):
    if entry.result.type == "succeeded":
        print(entry.result.message.content)
```

**TypeScript - 배치 생성 및 결과 조회:**
```typescript
await client.messages.batches.create({ requests: [...] });

const results = await client.messages.batches.results(batch_id);
for await (const entry of results) {
  if (entry.result.type === "succeeded") {
    console.log(entry.result.message.content);
  }
}
```

---

## 4. 베타 기능

베타 기능은 `client.beta` 네임스페이스로 접근하며 `betas` 파라미터에 헤더를 추가한다.

```python
# Python: Files API 베타
message = client.beta.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Please summarize this document."},
            {"type": "document", "source": {"type": "file", "file_id": "file_abc123"}},
        ],
    }],
    betas=["files-api-2025-04-14"],
)
```

베타 헤더 목록: https://platform.claude.com/docs/en/api/beta-headers

---

## 5. SDK 버전 및 GitHub 레포지토리

| SDK | 버전 확인 | GitHub |
|-----|----------|--------|
| Python Client SDK | `import anthropic; print(anthropic.__version__)` | https://github.com/anthropics/anthropic-sdk-python |
| TypeScript Client SDK | `npm list @anthropic-ai/sdk` | https://github.com/anthropics/anthropic-sdk-typescript |
| Python Agent SDK | `pip show claude-agent-sdk` | https://github.com/anthropics/claude-agent-sdk-python |
| TypeScript Agent SDK | `npm list @anthropic-ai/claude-agent-sdk` | https://github.com/anthropics/claude-agent-sdk-typescript |
| Python Agent SDK 데모 | - | https://github.com/anthropics/claude-agent-sdk-demos |
