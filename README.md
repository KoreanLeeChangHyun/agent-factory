# Agent Factory

Agent Factory 관련 프로젝트를 하나의 작업공간에서 관리하는 상위 저장소입니다.
각 프로젝트는 독립적인 Git 저장소이며 submodule로 연결되어 있습니다.

## 프로젝트 구성

| 경로 | 프로젝트 | 브랜치 |
| --- | --- | --- |
| `plugin/` | Codex plugin | `main` |
| `extension/` | VS Code extension | `main` |
| `web/` | Web application | `develop` |

## 클론

submodule을 포함해 한 번에 클론합니다.

```bash
git clone --recurse-submodules git@github.com:KoreanLeeChangHyun/agent-factory.git
cd agent-factory
```

이미 상위 저장소만 클론했다면 submodule을 초기화합니다.

```bash
git submodule update --init --recursive
```

## 업데이트

상위 저장소와 각 submodule의 지정 브랜치를 함께 업데이트합니다.

```bash
git pull
git submodule update --init --remote --recursive
```

각 프로젝트에서 직접 작업할 때는 해당 디렉터리로 이동합니다.

```bash
cd plugin    # 또는 extension, web
git status
```

submodule의 새 커밋을 상위 저장소에 반영하려면 상위 디렉터리에서 변경된 포인터를 커밋합니다.

```bash
cd ..
git add plugin extension web
git commit -m "Update component revisions"
git push
```
