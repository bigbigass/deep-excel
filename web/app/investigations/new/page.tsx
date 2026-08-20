import { InvestigationCreateForm } from "@/components/investigation-create-form";

const INVESTIGATION_STEPS = [
  {
    title: "建立问题范围",
    detail: "用一句明确的问题约束调查，并上传测量值、规格限和生产上下文。"
  },
  {
    title: "生成确定性证据",
    detail: "系统检查数据质量、SPC 信号、变化时间、分组差异和关联因素。"
  },
  {
    title: "验证候选根因",
    detail: "AI 只能基于证据提出候选原因，现场人员通过检查或试验确认或排除。"
  }
];

export default function NewInvestigationPage() {
  return (
    <div className="page page-reveal">
      <section className="page-header investigation-page-header">
        <p className="page-header__eyebrow">质量异常调查</p>
        <div className="page-header__title-row">
          <div>
            <h1 className="page-header__title">从异常现象出发，建立可验证的证据链</h1>
            <p className="page-header__subtitle">
              这里不是动态选择报告模板。系统会先完成统计调查，再让 AI 决定还需要查什么、哪些原因值得验证，以及缺少哪些数据。
            </p>
          </div>
        </div>
      </section>

      <div className="home-layout investigation-entry-layout">
        <div className="home-overview">
          <section className="hero-panel investigation-intro-panel">
            <div>
              <p className="hero-panel__eyebrow">调查主线</p>
              <h2 className="hero-panel__title">事实、关联和候选根因分层呈现</h2>
              <p className="hero-panel__subtitle">
                数学计算由程序完成，AI 只负责规划调查、整合证据和提出待验证假设。任何确认结果都必须记录人工操作者和验证说明。
              </p>
            </div>

            <div className="process-strip">
              {INVESTIGATION_STEPS.map((step, index) => (
                <div key={step.title} className="process-step">
                  <span className="process-step__index">{index + 1}</span>
                  <div className="process-step__title">{step.title}</div>
                  <p>{step.detail}</p>
                </div>
              ))}
            </div>

            <div className="investigation-principles">
              <div>
                <strong>程序计算</strong>
                <span>SPC、变化点、风险比、显著性和效应量</span>
              </div>
              <div>
                <strong>AI 调查</strong>
                <span>选择白名单工具、引用证据、形成候选假设</span>
              </div>
              <div>
                <strong>人工决定</strong>
                <span>现场验证、确认或排除、保留责任记录</span>
              </div>
            </div>
          </section>
        </div>

        <div className="home-operations">
          <InvestigationCreateForm />
        </div>
      </div>
    </div>
  );
}
