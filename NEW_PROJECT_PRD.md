# Product Requirements Document (PRD): Local Agent Studio (Next.js Multi-Agent Platform)

### 로컬 환경 스펙
- CPU: AMD Ryzen 9 9900X
- RAM: 64.0 GB
- GPU: NVIDIA GeForce RTX 5080 16GB
- OS: Windows 11

### Conda 가상환경
 - local-agent-studio

## 1. Project Overview
새로운 로컬 AI 다중 에이전트(Multi-Agent Swarm) 프로젝트입니다. 단일 대화형 모델이 아닌, 여러 개의 작고 특화된 로컬 모델(라우터, 코더, 검수자, 번역기 등)들이 동시에 협업하는 과정을 시각적으로 보여주고 효율적으로 오케스트레이션하는 인터랙티브 웹 애플리케이션 플랫폼을 구축합니다.

## 2. Tech Stack & Architecture
- **Frontend**: Next.js (App Router), React, Tailwind CSS, TypeScript
- **UI Components**: Shadcn UI, Framer Motion (에이전트 통신 및 사고 과정 애니메이션 렌더링)
- **Visual Node Editor**: React Flow (에이전트 군집/Topology 구성 및 실시간 데이터 흐름 시각화)
- **Backend (API Layer)**: Python (FastAPI) + LangGraph 또는 CrewAI (에이전트 오케스트레이션 비즈니스 로직)
- **Local AI Provider**: llama.cpp, Ollama, vLLM을 활용한 다중 포트(Port) 모델 호스팅 (추후 독립된 `LocalAI Studio`(경로 : Workspace\LocalAI-Studio) 샌드박스의 API를 끌어다 쓸 수 있도록 설계). OpenAI 호환 API 규격 사용.

## 3. Core Features
### 3.1. Agent Swarm Configurator 
- 사용자가 각 모델 노드(Node)를 역할별로 화면에 드래그 앤 드롭으로 배치. 
- 허깅페이스에서 최신 모델들을 자세하게 조사 비교하여 최고의 성능을 내는 모델들을 선정하여 사용
- 예: [User] ➡️ [Router(Qwen 3B)] ➡️ 분기 ➡️ [Coder(7B)] / [Math Prover(4B)] ➡️ 통합 ➡️ [Synthesizer(Llama 8B)]

### 3.2. Real-time Output & "Thinking" Visualization
- 에이전트들이 서로 대화하는 과정을 실시간 소켓/SSE로 시각화 (예: 노드와 노드 사이를 이동하는 데이터 패킷 빛 애니메이션).
- 터미널이나 일방적인 단일 프롬프트 출력이 아닌 넷플릭스 뺨치는 화려하고 모던한 모니터링 UI 디자인 적용.

### 3.3. Task Management Dashboard
- 각 에이전트의 VRAM 사용량, 생성 속도(Tokens/s), 응답 지연 시간(Latency) 등을 모니터링하는 패널 탑재.

## 4. UI/UX Design Guidelines (Strict)
- **Aesthetics First**: 이 앱은 디자인적으로 완벽하게 "프리미엄(Premium)"이어야 합니다. 어둡고 매끄러운 다크 모드(Glassmorphism), 눈부시지 않고 조화로운 그라데이션, 그리고 사용자의 시선을 끄는 부드러운 마이크로 애니메이션 애니메이션(Framer Motion)을 필수 도입합니다. 기본 브라우저 텍스트는 절대 사용을 금지하며 Inter 또는 Roboto 같은 구글 폰트를 사용합니다. 단순한 MVP가 아닙니다. 누가 봐도 미래의 AI 통제실 같은 느낌(Cyberpunk/Sci-Fi 또는 극단적인 Apple식 미니멀리즘)이 들어야 합니다.

## 5. Development Phases
1. **Initial Setup (Next.js 기반 기초 공사)**: Next.js + Tailwind + Shadcn 빈 프로젝트 세팅 및 레이아웃(Sidebar, Main Canvas, Right panel) 배치.
2. **React Flow Integration**: 메인 캔버스 영역에 모델과 에이전트를 조립할 수 있는 노드 에디터 도입.
3. **Python FastAPI Backend Setup**: 프론트엔드와 데이터(프롬프트 스레드, 시스템 로깅)를 실시간으로 주고받을 별도 백엔드 기초 폴더 생성 및 소켓 설정.
4. **Agent Orchestration Logic (LangGraph/CrewAI)**: 사용자의 요청을 각각의 로컬 API 포트로 분배하고 모으는 파이썬 라우팅 로직 구현.
5. **Real-time Synchronization**: 모델이 추론 및 대화하는 과정을 Next.js 프론트 화면 애니메이션으로 연결.

**Note to the Agent in the new session:**
- 이 PRD를 읽자마자 위의 기술 스택을 활용하여 `npx create-next-app` 명령어부터 즉시 시작해 주세요. 사용자가 오케이 할 때까지 화려한 UI를 짜는 데 집중해 주시고, 1차 마일스톤은 백엔드 완성 전 프론트엔드(React Flow + Dashboard) 레이아웃의 시각적 완성입니다.

---

## 6. Current Implementation Status (v0.2.0)
현재 코드베이스를 분석한 결과 PRD에 기재된 **개발 페이즈(1~5)가 90% 이상 훌륭하게 구현 완료되었습니다.**

- **프론트엔드(Next.js)**: `AgentCanvas`, `NodeConfigPanel`, `RightPanel` 등을 통해 React Flow 기반의 에이전트 노드 구성과 UI 테마(다크 모드, Glassmorphism)가 성공적으로 셋업되었습니다.
- **백엔드(FastAPI)**: `main.py`와 `pipeline`을 통해 에이전트 오케스트레이션 로직이 구현되었고, `/api/run` SSE를 통해 실시간 "Thinking" 프로세스와 스트리밍 통신이 가능하도록 완비되었습니다. 허깅페이스 모델 다운로드 파이프라인도 구축되었습니다.

## 7. Future Milestones & Enhancements (추가 개발 제안)
초기 1차 마일스톤(프론트엔드 레이아웃 및 백엔드 파이프라인 연동)이 완성되었으므로, 플랫폼을 더욱 고도화하기 위한 다음 페이즈를 제안합니다.

1. **Phase 6: 캔버스와 플로우 저장소 구축 (Persistent Storage)**
   - 구축한 에이전트 라우팅 토폴로지(노드 연결 정보)를 JSON 등 프리셋으로 DB(SQLite/PostgreSQL)에 **저장/불러오기 기능** 추가.
   - 이전 채팅 및 추론 로그(History)를 보관하기 위한 RAG 기반 워크스페이스 세션 관리 기능.
2. **Phase 7: Advanced RAG / Tools Integration (확장 기능)**
   - 각 Agent 노드가 특정 도구(웹 검색, 파일 시스템 접근, 터미널 실행 등)를 장착할 수 있는 **Tools Configuration UI** 추가.
   - 캔버스에서 RAG 데이터를 업로드할 수 있는 문서 임베딩 노드 지원.
3. **Phase 8: 심화 모니터링 및 성능 최적화 (Metrics Dashboard)**
   - vLLM/llama.cpp 샌드박스의 **실시간 VRAM 그래프, 모델별 토큰 생성 속도(Tokens/s) 차트**를 대시보드(RightPanel)에 시각적으로 연동.
   - 노드 흐름 중 병목이 생기는 구간에 대한 경고 UI 시각화.
4. **Phase 9: 다중 노드 병렬 처리 (Parallel Pipeline Execution)**
   - 라우터가 2개 이상의 에이전트(Coder, Math 등)에게 작업을 병렬 분배하고, Synthesizer가 응답을 취합하는 **복잡한 브랜칭 로직 완벽 제어.**
