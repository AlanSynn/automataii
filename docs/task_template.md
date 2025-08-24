ultrathink 당신은 전설적인 개발자로서 jeff dean, kent beck, rob pike, ken tompson 의 소울을
  가지고 있습니다. blueprint generation 할때 모든 mechanism 도 generating 하는거
  맞지? 필요한 모든 컴포넌트들 조립에 필요한 모든 사항들. 해당 코드베이스 를 확인 후
   깊게 생각 해보세요. 해당 프로젝트가 {주제}의 기능을 제대로 하고있나요? 만약
  그렇지않다면 CLAUDE.md  을 작성하고 주도적으로 생각해서 진행하세요. 이전의
  CLAUDE.md는 .deprecated 로 outdated 처리 하세요.

지금 mechanism_design_tab 의 작동이 원활하지 못하다. 다른 탭과 연동이 많이 되어있어서 인것 같은데, 다른 탭에서 넘어온 정보가 없을때 그러니까 테스트 하는 경우 작동성을 검증할 수 있는 방법이 모든 탭에 필요하다. Ultrathink
1. 해당 코드베이스 를 확인 후 깊게 생각 해보세요. 해당 프로젝트가 {주제}의 기능을 제대로 하고있나요? 만약 그렇지않다면 CLAUDE.md  을 작성하고 주도적으로 생각해서 진행하세요.

2. 테스트는 tests 폴더에 잘 정리해가면서 해야한다. 설계 - 구현 - 검증 - 피드백의 과정을 루프를 돌면서 모든 체크리스트를
완료할때 까지 진행해라. 허용되는 명령어는 .claude 에 있으니 이 안에서만 해야한다.
3. 다음 단계를 진행하세요 CLAUDE.md 을 체크 리스트로 체크하면서 구현 후 업데이트 하고 진행 하세요. 모든 체크리스트가 구현 될때까지 쉬지 마세요.
4. 모든 체크리스트가 구현 되었으면 다음 단계를 진행하세요. CLAUDE.md 를 확인하고 모든 체크리스트가 완료되었는지 확인하세요.
5. 완료되었으면 completed_task_<task_name>_<date>.md 로 이름을 바꾸고 완료된 테스크를 저장하세요. tasks/ 에 저장하세요.


# Task Execution Framework

## Phase 1: Deep Analysis & Planning
**UltraThink Mode**: Channel the engineering excellence of Jeff Dean, Kent Beck, Rob Pike, and Ken Thompson.

Analyze the current codebase deeply:
- Does this project properly implement {주제} functionality?
- If not, create CLAUDE.md with comprehensive action plan
- Move previous CLAUDE.md to .deprecated folder

## Phase 2: Test-Driven Development
- Organize all tests in `tests/` folder
- Follow iterative cycle: Design → Implement → Verify → Feedback
- Use only commands specified in `.claude` file
- Continue until all checklist items are completed

## Phase 3: Implementation & Verification
- Progress through CLAUDE.md checklist systematically
- Update checklist status after each implementation
- Do not stop until all items are implemented

## Phase 4: Completion Validation
- Verify all checklist items in CLAUDE.md are completed
- Ensure full functionality and test coverage
- **Commit**: Use `gcllm "All features implemented and validated"`

## Phase 5: Task Archival
- Rename completed task to `completed_task_<task_name>_<date>.md`
- Store in `tasks/` directory for future reference