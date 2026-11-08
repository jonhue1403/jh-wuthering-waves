# Automation capability matrix

Candidate scope: CORE_AND_ROUTES, 8 November 2026. Status describes this
candidate, not upstream author reports or historical live runs. Registration is
in `config.py`; language filters can hide unsupported tasks.

| Game/native capability | Upstream task/helper | JH task or adapter | Registration/profile | Evidence | Genuine remaining gap |
| --- | --- | --- | --- | --- | --- |
| Shared task scheduling | OK TaskExecutor, run_task_by_class | Session, guarded interaction, AutomationSessionTask | One-time controls; existing executor reused | Actual 3.0.4 adapter tests; runtime startup/discovery | Live pause/takeover/cleanup on matching-privilege game |
| Current Waveplate claims | BaseWWTask.use_stamina | Explicit budget, durable journal, strict cost/debit verification | Applies to inherited claims; no-reserve default | ResourceClaims, ResourceGoals | Compatible plain/split/result fixtures and live spending |
| Guidebook ascension target | PR1837 CultivationTask | Adapted CultivationTask | One-time, zh_CN/16:9; preview default | Adapted task tests; exact PR source studied | Current Chinese UI, observed identity/reset, live actual inventory |
| General material goals | No general source mapper | ResourceRoutineTask, ResourceGoalQueue | One-time/schedulable; labelled JSON plans, preview default | Queue/orchestration tests | Real exact boss/domain/mob/drop mappings; unknowns unresolved |
| Daily tasks/rewards | DailyTask | Qualified routine observer + durable completion key | Inherited one-time/schedulable | Daily/scheduling/recovery regressions | Current completion/reward observation profiles and repeat live sessions |
| Tacet/Forgery/Simulation | TacetTask/ForgeryTask/SimulationTask | Shared session, budgets, debit journal | Existing registrations | Recovery, claim, scheduling tests | Current reward receipts and live bounds |
| Weekly boss material rewards | FarmEchoTask farms Echoes | Separate weekly eligibility state | No qualified weekly-material adapter enabled | Routine tests refuse unresolved eligibility | Remaining material-claim eligibility/reward screens |
| Boss Echo farming | FarmEchoTask | Existing combat/recovery plus semantic challenge confirmations | Existing registration; reward spend still gated | Teleport/pickup/echo-rate/recovery tests | Current live repeat/cancellation; Echo success never material receipt |
| Nightmare Nest | NightmareNestTask | Existing dispatch with failure propagation | Existing registration | Nightmare/schedule tests | Actual reward and skip-completed loop |
| Fantasies/Weekly Activity | GardenTask | Legacy Remnant Crystal claim clicks removed; qualified Weekly Activity observer gate | Current profile absent, blocks outdated claim flow | Resource/observer tests | Actual current Weekly Activity migration screenshots and loop |
| Watch story/cutscenes | AutoDialogTask normally skips | StoryWatchTask; durable no-skip and incompatible-trigger guards | One-time; no observed segment bundled | StoryWatch + existing dialogue regressions | One actual travel/dialogue/combat segment; native Semi-Auto qualification |
| Single surface camp | JH HuntController/locator/follower | HuntMobTask retains exactly one camp | Localization-only default; runtime-bound sidecar required for input | Existing hunt/navigation/calibration tests | 3.0.4 walk, combat clear, independent eligible respawn sessions |
| Bounded material route | Existing controller/planner/OK adapter | Separate BoundedRouteTask/manifest | Preview/localization default; max three reviewed camps | Route/inventory/beacon offline tests | Verified drop/item inventory and connecting segments; no real route enabled |
| Known-beacon transition | Existing travel helpers | Reviewed bounded loading/destination-localization transition | Separate evidence gate | Route transition tests | Actual loading/destination observations; no arbitrary map travel |
| Material Locator/Blitz | Version-dependent native UI | No fabricated controls | Disabled/unresolved | No compatible screenshots supplied | Observe installed version and real compatible screens |
| Echo destruction/enhancement/main-stat consumption | Merge/Enhance/Change/FiveToOne | Shared policy refuses unqualified valuable-item consumption | Existing cards retained, live execution blocked by policy | Eligibility/source review | Optional later scope; no expansion in this candidate |

Historical camp evidence remains one combat-and-clear trial. An empty-camp
return on 2.0.7b1 is a distinct observation, not a second combat trial or a
qualification of 3.0.4. See [live gates](LIVE-QUALIFICATION.md).
