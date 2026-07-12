"""
EU AI Act risk classification and assessment engine.

Implements:
  - Annex III high-risk category classifier
  - Article 5 prohibited use detector
  - Conformity assessment requirement generator (Arts. 9-20, 26-27)
  - Compliance score calculator
  - Technical documentation generator (Annex IV structure)
  - EU Declaration of Conformity generator (Art. 47)
  - FRIA generator (Art. 27)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.db.models.euai import (
    AiAnnexIIICategory,
    AiActAssessment,
    AiActRequirementCheck,
    AiSystem,
    AiRiskLevel,
    AiSystemRole,
    AssessmentStatus,
    DocumentType,
    RegistrationStatus,
    RequirementStatus,
)
from app.db.schemas.euai import ClassificationAnswers, ClassificationResult


# ── Risk Classification ───────────────────────────────────────────────────────

def classify_risk(
    system: AiSystem,
    answers: ClassificationAnswers,
) -> ClassificationResult:
    """
    Classify an AI system's risk level based on questionnaire answers.
    Returns full classification result with obligations summary.
    """

    # 1. Check Article 5 — Prohibited Practices (Unacceptable Risk)
    prohibition_reason = _check_prohibited(answers)
    if prohibition_reason:
        return ClassificationResult(
            risk_level=AiRiskLevel.UNACCEPTABLE,
            annex_iii_category=AiAnnexIIICategory.NONE,
            is_prohibited=True,
            prohibition_reason=prohibition_reason,
            key_obligations=["This AI system must NOT be placed on the EU market or put into service (Article 5)."],
            registration_required=False,
            summary=(
                f"PROHIBITED: This system falls under Article 5 of the EU AI Act and cannot be "
                f"deployed in the EU. Reason: {prohibition_reason}"
            ),
        )

    # 2. Check Annex III — High-Risk categories
    annex_category = _classify_annex_iii(answers)
    is_high_risk = annex_category != AiAnnexIIICategory.NONE or system.is_safety_component

    # GPAI with systemic risk also carries Chapter V obligations
    gpai_systemic = system.is_gpai and (
        system.gpai_systemic_risk or
        (answers.training_compute_flops and answers.training_compute_flops >= 1e25)
    )

    if is_high_risk:
        obligations = _provider_high_risk_obligations() if system.role in (AiSystemRole.PROVIDER, AiSystemRole.BOTH) else []
        obligations += _deployer_high_risk_obligations() if system.role in (AiSystemRole.DEPLOYER, AiSystemRole.BOTH) else []

        return ClassificationResult(
            risk_level=AiRiskLevel.HIGH,
            annex_iii_category=annex_category,
            is_prohibited=False,
            prohibition_reason=None,
            key_obligations=obligations,
            registration_required=True,
            summary=(
                f"HIGH RISK: This system falls under Annex III category '{annex_category.value}'. "
                f"Full conformity assessment required before deployment. "
                f"Registration in EU database mandatory (Article 49)."
            ),
        )

    # 3. GPAI — Chapter V obligations (not Annex III but still significant)
    if system.is_gpai:
        obligations = [
            "Maintain technical documentation (Article 53 + Annex XI)",
            "Publish summary of training data (Article 53)",
            "Comply with EU copyright law",
            "Provide model card to downstream providers",
        ]
        if gpai_systemic:
            obligations += [
                "Adversarial testing / red-teaming (Article 55)",
                "Report serious incidents to AI Office (Article 55)",
                "Cybersecurity safeguards (Article 55)",
            ]
        return ClassificationResult(
            risk_level=AiRiskLevel.HIGH if gpai_systemic else AiRiskLevel.LIMITED,
            annex_iii_category=AiAnnexIIICategory.NONE,
            is_prohibited=False,
            prohibition_reason=None,
            key_obligations=obligations,
            registration_required=gpai_systemic,
            summary=(
                f"GENERAL PURPOSE AI MODEL {'with systemic risk' if gpai_systemic else ''}: "
                f"Chapter V obligations apply."
            ),
        )

    # 4. Limited Risk — Transparency obligations only (Article 50)
    if answers.is_chatbot or answers.generates_deepfakes or answers.emotion_recognition_limited:
        return ClassificationResult(
            risk_level=AiRiskLevel.LIMITED,
            annex_iii_category=AiAnnexIIICategory.NONE,
            is_prohibited=False,
            prohibition_reason=None,
            key_obligations=[
                "Disclose AI-generated or synthetic content (Article 50)",
                "Inform users they are interacting with an AI system",
                "Label deepfake/synthetic media as AI-generated",
            ],
            registration_required=False,
            summary="LIMITED RISK: Transparency obligations under Article 50 apply.",
        )

    # 5. Minimal Risk
    return ClassificationResult(
        risk_level=AiRiskLevel.MINIMAL,
        annex_iii_category=AiAnnexIIICategory.NONE,
        is_prohibited=False,
        prohibition_reason=None,
        key_obligations=[
            "No mandatory obligations under the EU AI Act",
            "Voluntary codes of conduct recommended (Article 95)",
            "AI literacy requirements apply to all operators (Article 4)",
        ],
        registration_required=False,
        summary="MINIMAL RISK: No specific EU AI Act obligations. Voluntary codes of conduct encouraged.",
    )


def _check_prohibited(answers: ClassificationAnswers) -> Optional[str]:
    if answers.social_scoring_by_public:
        return "Social scoring of natural persons by public authorities (Article 5(1)(c))"
    if answers.real_time_remote_biometric_public:
        return "Real-time remote biometric identification in publicly accessible spaces for law enforcement (Article 5(1)(h))"
    if answers.subliminal_manipulation:
        return "Subliminal manipulation of persons causing harm (Article 5(1)(a))"
    if answers.exploits_vulnerability:
        return "Exploitation of vulnerabilities of specific groups (Article 5(1)(b))"
    return None


def _classify_annex_iii(answers: ClassificationAnswers) -> AiAnnexIIICategory:
    if answers.uses_biometrics and answers.biometric_purpose in (
        "remote_id", "categorisation", "emotion"
    ):
        return AiAnnexIIICategory.BIOMETRICS

    if answers.is_critical_infrastructure:
        return AiAnnexIIICategory.CRITICAL_INFRASTRUCTURE

    if answers.education_purpose in ("admission", "evaluation", "monitoring"):
        return AiAnnexIIICategory.EDUCATION

    if answers.employment_purpose in ("recruitment", "performance", "termination", "task_allocation"):
        return AiAnnexIIICategory.EMPLOYMENT

    if answers.essential_service_purpose in ("benefits", "credit", "insurance", "emergency"):
        return AiAnnexIIICategory.ESSENTIAL_SERVICES

    if answers.law_enforcement_use:
        return AiAnnexIIICategory.LAW_ENFORCEMENT

    if answers.migration_use:
        return AiAnnexIIICategory.MIGRATION

    if answers.justice_use or answers.electoral_influence:
        return AiAnnexIIICategory.JUSTICE_DEMOCRACY

    return AiAnnexIIICategory.NONE


def _provider_high_risk_obligations() -> list[str]:
    return [
        "Establish risk management system (Article 9)",
        "Implement data and data governance practices (Article 10)",
        "Prepare technical documentation per Annex IV (Article 11)",
        "Enable automatic event logging / record-keeping (Article 12)",
        "Provide transparency information to deployers (Article 13)",
        "Design human oversight measures (Article 14)",
        "Ensure accuracy, robustness and cybersecurity (Article 15)",
        "Establish quality management system (Article 17)",
        "Register system in EU database before placing on market (Article 49)",
        "Post-market monitoring plan (Article 72)",
    ]


def _deployer_high_risk_obligations() -> list[str]:
    return [
        "Use system in accordance with provider instructions (Article 26)",
        "Assign human oversight responsibility (Article 26)",
        "Monitor system for risks during use (Article 26)",
        "Maintain logs for minimum 6 months (Article 26)",
        "Report serious incidents or malfunctions (Article 26)",
        "Conduct Fundamental Rights Impact Assessment if public authority (Article 27)",
    ]


# ── Assessment Requirement Generator ─────────────────────────────────────────

# Full requirement catalogue keyed by (assessment_type, article)
_PROVIDER_REQUIREMENTS: list[dict] = [
    {
        "article": "Art. 4",
        "article_title": "AI Literacy",
        "requirement_text": (
            "Ensure sufficient AI literacy of staff and all persons dealing with the operation and "
            "use of the AI system on behalf of the provider."
        ),
        "guidance": (
            "Document training programmes, competency assessments, and ongoing education on AI risks, "
            "capabilities, and limitations."
        ),
    },
    {
        "article": "Art. 9",
        "article_title": "Risk Management System",
        "requirement_text": (
            "Establish, implement, document and maintain a risk management system throughout the "
            "entire lifecycle of the high-risk AI system."
        ),
        "guidance": (
            "The risk management system must: (1) identify and analyse known and reasonably foreseeable risks, "
            "(2) estimate and evaluate risks from intended use and misuse, "
            "(3) implement risk mitigation measures, "
            "(4) test the system to identify residual risks."
        ),
    },
    {
        "article": "Art. 10",
        "article_title": "Data and Data Governance",
        "requirement_text": (
            "Training, validation and testing datasets must be subject to data governance and management "
            "practices appropriate for the intended purpose."
        ),
        "guidance": (
            "Document: data collection methodology, data preparation steps, bias identification and mitigation, "
            "dataset representativeness analysis, data quality metrics."
        ),
    },
    {
        "article": "Art. 11",
        "article_title": "Technical Documentation (Annex IV)",
        "requirement_text": (
            "Draw up technical documentation before placing the system on the market. "
            "Documentation must contain all information specified in Annex IV."
        ),
        "guidance": (
            "Annex IV requires: general system description, design specs, training methodology, "
            "validation/testing procedures, monitoring and logging info, performance metrics, "
            "cybersecurity measures, and instructions of use."
        ),
    },
    {
        "article": "Art. 12",
        "article_title": "Record-Keeping",
        "requirement_text": (
            "The system must be designed to enable automatic logging of events throughout its lifecycle "
            "to ensure traceability and post-incident analysis."
        ),
        "guidance": (
            "Logs should capture: system activations, decision outputs, anomalies, "
            "human override events, and system performance metrics."
        ),
    },
    {
        "article": "Art. 13",
        "article_title": "Transparency to Deployers",
        "requirement_text": (
            "Ensure sufficient transparency to deployers via clear instructions of use, "
            "including capabilities, limitations, and human oversight requirements."
        ),
        "guidance": (
            "Instructions of use must include: intended purpose, performance metrics per population group, "
            "known risks, human oversight requirements, technical infrastructure needed, "
            "and maintenance information."
        ),
    },
    {
        "article": "Art. 14",
        "article_title": "Human Oversight",
        "requirement_text": (
            "Design the system to enable effective human oversight, including the ability to understand, "
            "interpret, override, stop and correct the system."
        ),
        "guidance": (
            "Implement: override/stop mechanisms, output interpretation tools, alerts for out-of-distribution inputs, "
            "and training for operators on human oversight responsibilities."
        ),
    },
    {
        "article": "Art. 15",
        "article_title": "Accuracy, Robustness and Cybersecurity",
        "requirement_text": (
            "Achieve appropriate levels of accuracy, robustness and cybersecurity throughout the lifecycle, "
            "with resilience against errors, faults and adversarial attacks."
        ),
        "guidance": (
            "Provide accuracy metrics, conduct adversarial robustness testing, "
            "implement input validation, monitor for performance degradation, "
            "and apply cybersecurity standards (e.g. ENISA guidelines)."
        ),
    },
    {
        "article": "Art. 16",
        "article_title": "Provider Obligations",
        "requirement_text": (
            "Ensure the high-risk AI system complies with all requirements before placing on the market, "
            "including CE marking where applicable."
        ),
        "guidance": (
            "Complete conformity assessment per Article 43, prepare EU Declaration of Conformity (Article 47), "
            "affix CE marking where required, and register in EU database (Article 49)."
        ),
    },
    {
        "article": "Art. 17",
        "article_title": "Quality Management System",
        "requirement_text": (
            "Put in place a quality management system covering all aspects of compliance, "
            "including strategy, design, development, testing and post-market activities."
        ),
        "guidance": (
            "QMS must cover: compliance strategy, data management, design controls, "
            "testing and validation procedures, post-market monitoring, incident reporting."
        ),
    },
    {
        "article": "Art. 20",
        "article_title": "Corrective Actions and Incident Reporting",
        "requirement_text": (
            "Take necessary corrective actions if the system does not conform with requirements, "
            "and report serious incidents to market surveillance authorities."
        ),
        "guidance": (
            "Define incident severity thresholds, establish reporting workflows, "
            "and document all corrective actions taken."
        ),
    },
    {
        "article": "Art. 72",
        "article_title": "Post-Market Monitoring",
        "requirement_text": (
            "Establish, document and implement a post-market monitoring plan to actively monitor "
            "performance and risks in real-world conditions."
        ),
        "guidance": (
            "Post-market monitoring plan should include: KPIs, monitoring frequency, "
            "feedback mechanisms from deployers, and update/recall procedures."
        ),
    },
]

_DEPLOYER_REQUIREMENTS: list[dict] = [
    {
        "article": "Art. 4",
        "article_title": "AI Literacy",
        "requirement_text": (
            "Ensure sufficient AI literacy of all persons responsible for the operation of the AI system."
        ),
        "guidance": "Provide training on the AI system's capabilities, limitations, and human oversight duties.",
    },
    {
        "article": "Art. 26(1)",
        "article_title": "Use Per Provider Instructions",
        "requirement_text": (
            "Use the high-risk AI system in accordance with the provider's instructions of use."
        ),
        "guidance": (
            "Retain the provider's instructions of use, ensure staff are trained on them, "
            "and document that the system is used only for its intended purpose."
        ),
    },
    {
        "article": "Art. 26(2)",
        "article_title": "Human Oversight Assignment",
        "requirement_text": (
            "Assign human oversight of the AI system to persons with the necessary competence, "
            "authority and resources."
        ),
        "guidance": "Document oversight roles and responsibilities, and provide relevant training.",
    },
    {
        "article": "Art. 26(5)",
        "article_title": "Log Retention",
        "requirement_text": (
            "Keep automatically generated logs for at least 6 months, unless Union or national law "
            "requires a longer period."
        ),
        "guidance": "Implement log retention policies and access controls for audit purposes.",
    },
    {
        "article": "Art. 26(6)",
        "article_title": "Risk Monitoring During Use",
        "requirement_text": (
            "Monitor the operation of the system based on the provider's instructions and report "
            "any serious incidents or malfunctions."
        ),
        "guidance": (
            "Define monitoring frequency and metrics. Establish escalation path for incidents. "
            "Report serious incidents to provider and relevant authority within applicable deadlines."
        ),
    },
    {
        "article": "Art. 26(7)",
        "article_title": "Transparency to Affected Persons",
        "requirement_text": (
            "Inform natural persons that they are subject to the use of a high-risk AI system "
            "where this is required under applicable law."
        ),
        "guidance": "Publish AI usage notice where legally required (e.g. recruitment, credit scoring, benefits).",
    },
]

_FRIA_REQUIREMENTS: list[dict] = [
    {
        "article": "Art. 27(1)",
        "article_title": "FRIA — Scope Determination",
        "requirement_text": (
            "Determine whether the organisation qualifies as a body governed by public law or "
            "an operator providing public services, triggering FRIA obligation."
        ),
        "guidance": (
            "FRIA is mandatory for: public authorities, bodies governed by public law, "
            "and private operators providing public services using high-risk AI."
        ),
    },
    {
        "article": "Art. 27(2a)",
        "article_title": "FRIA — System Description",
        "requirement_text": (
            "Describe the high-risk AI system, its intended purpose and the period and geographic scope "
            "of intended use."
        ),
        "guidance": "Include system name, version, provider, deployment context, and affected populations.",
    },
    {
        "article": "Art. 27(2b)",
        "article_title": "FRIA — Fundamental Rights Inventory",
        "requirement_text": (
            "Identify and list the categories of natural persons and groups likely to be affected "
            "by the AI system in the context of its intended use."
        ),
        "guidance": (
            "Consider: protected characteristics (age, gender, ethnicity, disability), "
            "vulnerable groups, and disproportionate impacts."
        ),
    },
    {
        "article": "Art. 27(2c)",
        "article_title": "FRIA — Rights Impact Assessment",
        "requirement_text": (
            "Identify and assess the specific risks to fundamental rights including dignity, "
            "non-discrimination, privacy, freedom of expression, and access to justice."
        ),
        "guidance": (
            "For each identified risk: assess likelihood, severity, and reversibility. "
            "Reference relevant EU Charter of Fundamental Rights articles."
        ),
    },
    {
        "article": "Art. 27(2d)",
        "article_title": "FRIA — Mitigation Measures",
        "requirement_text": (
            "Describe the specific measures planned to address identified risks, including "
            "human oversight, technical safeguards, and redress mechanisms."
        ),
        "guidance": (
            "Mitigation measures should address: bias monitoring, appeal mechanisms, "
            "human review for high-stakes decisions, and data minimisation."
        ),
    },
    {
        "article": "Art. 27(3)",
        "article_title": "FRIA — Consultation",
        "requirement_text": (
            "Consult with the relevant market surveillance authority and, where applicable, "
            "with the data protection authority before deploying the system."
        ),
        "guidance": "Document consultation dates, authorities consulted, and their feedback.",
    },
]


def generate_assessment_requirements(
    assessment_type: str,
) -> list[dict]:
    """Return ordered list of requirement dicts for the given assessment type."""
    if assessment_type == "provider":
        reqs = _PROVIDER_REQUIREMENTS
    elif assessment_type == "deployer":
        reqs = _DEPLOYER_REQUIREMENTS
    elif assessment_type == "fria":
        reqs = _FRIA_REQUIREMENTS
    else:
        reqs = _PROVIDER_REQUIREMENTS

    return [dict(r, sort_order=i) for i, r in enumerate(reqs)]


# ── Compliance Score Calculator ───────────────────────────────────────────────

def calculate_compliance_score(assessment: AiActAssessment) -> float:
    """
    Calculate 0-100 compliance score.
    Compliant = 1.0 point, Partial = 0.5, Non-compliant = 0, Not applicable excluded.
    """
    checks = assessment.requirement_checks
    applicable = [c for c in checks if c.status != RequirementStatus.NOT_APPLICABLE and c.status != RequirementStatus.PENDING]

    if not applicable:
        return 0.0

    score_map = {
        RequirementStatus.COMPLIANT: 1.0,
        RequirementStatus.PARTIAL: 0.5,
        RequirementStatus.NON_COMPLIANT: 0.0,
    }
    total = sum(score_map.get(c.status, 0.0) for c in applicable)
    return round((total / len(applicable)) * 100, 1)


def update_assessment_counts(assessment: AiActAssessment) -> None:
    checks = assessment.requirement_checks
    assessment.compliant_count = sum(1 for c in checks if c.status == RequirementStatus.COMPLIANT)
    assessment.partial_count = sum(1 for c in checks if c.status == RequirementStatus.PARTIAL)
    assessment.non_compliant_count = sum(1 for c in checks if c.status == RequirementStatus.NON_COMPLIANT)
    assessment.not_applicable_count = sum(1 for c in checks if c.status == RequirementStatus.NOT_APPLICABLE)
    assessment.overall_score = calculate_compliance_score(assessment)

    pending = sum(1 for c in checks if c.status == RequirementStatus.PENDING)
    if pending == 0:
        assessment.status = AssessmentStatus.COMPLETED
        assessment.completed_at = datetime.now(timezone.utc)
    else:
        assessment.status = AssessmentStatus.IN_PROGRESS


# ── Document Generators ───────────────────────────────────────────────────────

def generate_technical_documentation(system: AiSystem) -> dict:
    """
    Generate Annex IV Technical Documentation structure.
    Returns structured JSON document content.
    """
    return {
        "document_type": "technical_documentation",
        "annex_reference": "Annex IV, Article 11",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_id": str(system.id),
        "sections": {
            "1_general_description": {
                "title": "1. General Description of the AI System",
                "content": {
                    "name": system.name,
                    "version": system.version,
                    "description": system.description or "",
                    "intended_purpose": system.intended_purpose,
                    "provider": system.provider_name or "[Provider Name]",
                    "deployment_sectors": system.deployment_sectors,
                    "role": system.role.value,
                    "eu_market": system.eu_market,
                },
                "status": "draft",
                "notes": "Complete with full system description, including the interaction between components.",
            },
            "2_design_and_development": {
                "title": "2. Detailed Description of Design and Development",
                "content": {
                    "design_choices": "[Describe key design choices and trade-offs]",
                    "algorithms_used": "[List algorithms and computational methods]",
                    "training_methodology": "[Describe training approach, architecture, hyperparameters]",
                    "hardware_requirements": "[CPU/GPU/memory requirements]",
                },
                "status": "pending",
                "notes": "Must include design specifications sufficient for understanding, auditing and replication.",
            },
            "3_data_governance": {
                "title": "3. Information on Training, Validation and Testing Data",
                "content": {
                    "datasets_used": "[List and describe all datasets]",
                    "data_sources": "[Describe data origins and collection methods]",
                    "data_preprocessing": "[Describe preprocessing and cleaning steps]",
                    "bias_assessment": "[Describe bias identification and mitigation measures]",
                    "representativeness": "[Describe how datasets are representative of intended use cases]",
                },
                "status": "pending",
                "notes": "Required under Article 10. Must demonstrate data quality and governance.",
            },
            "4_performance_metrics": {
                "title": "4. Validation and Testing Procedures and Results",
                "content": {
                    "validation_methodology": "[Describe validation approach]",
                    "test_datasets": "[Describe test data characteristics]",
                    "accuracy_metrics": "[Provide accuracy, precision, recall, F1 or relevant metrics]",
                    "performance_by_group": "[Show performance breakdown across demographic groups]",
                    "robustness_testing": "[Describe adversarial and edge-case testing]",
                },
                "status": "pending",
                "notes": "Must include metrics, benchmarks, and results demonstrating conformity.",
            },
            "5_monitoring_and_logging": {
                "title": "5. Monitoring, Functioning and Control",
                "content": {
                    "logging_capabilities": "[Describe automatic event logging mechanisms]",
                    "monitoring_metrics": "[List metrics monitored in production]",
                    "alerting_thresholds": "[Define performance degradation alerts]",
                    "human_override_mechanism": "[Describe how operators can override or stop the system]",
                },
                "status": "pending",
                "notes": "Required under Article 12. Logs must enable post-incident analysis.",
            },
            "6_transparency_instructions": {
                "title": "6. Instructions of Use for Deployers",
                "content": {
                    "intended_use_cases": "[Describe permitted use cases]",
                    "prohibited_uses": "[Describe uses outside scope]",
                    "performance_limitations": "[Describe known limitations and failure modes]",
                    "human_oversight_requirements": "[Specify required human oversight measures]",
                    "technical_prerequisites": "[Hardware, software, integration requirements]",
                    "maintenance_requirements": "[Update, recalibration and monitoring requirements]",
                },
                "status": "pending",
                "notes": "Required under Article 13. Must be clear and accessible to non-technical deployers.",
            },
            "7_cybersecurity": {
                "title": "7. Cybersecurity Measures",
                "content": {
                    "security_measures": "[Describe technical security controls]",
                    "threat_model": "[Describe known threats and mitigations]",
                    "penetration_testing": "[Describe security testing conducted]",
                    "incident_response": "[Describe cybersecurity incident response plan]",
                },
                "status": "pending",
                "notes": "Required under Article 15. Reference ENISA cybersecurity guidelines where applicable.",
            },
            "8_eu_declaration_reference": {
                "title": "8. EU Declaration of Conformity Reference",
                "content": {
                    "declaration_status": "[Draft/Signed]",
                    "conformity_assessment_procedure": "[Internal control (Annex VI) / Third-party (Annex VII)]",
                    "standards_applied": "[List harmonised standards or common specifications applied]",
                    "notified_body": "[If applicable: name and ID of notified body]",
                },
                "status": "pending",
                "notes": "Required under Article 47.",
            },
        },
        "completion_status": {
            "total_sections": 8,
            "completed_sections": 1,
            "completion_percentage": 12.5,
        },
    }


def generate_declaration_of_conformity(system: AiSystem) -> dict:
    """
    Generate EU Declaration of Conformity (Article 47, Annex V structure).
    """
    return {
        "document_type": "eu_declaration_of_conformity",
        "article_reference": "Article 47, Annex V",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_id": str(system.id),
        "content": {
            "provider_name": system.provider_name or "[Legal name of provider]",
            "provider_address": "[Registered address of provider]",
            "system_name": system.name,
            "system_version": system.version,
            "intended_purpose": system.intended_purpose,
            "risk_classification": system.risk_level.value if system.risk_level else "pending_classification",
            "annex_iii_category": system.annex_iii_category.value if system.annex_iii_category else "none",
            "conformity_assessment_procedure": "[Annex VI (internal control) or Annex VII (notified body)]",
            "harmonised_standards_applied": [
                "[List applicable harmonised standards]"
            ],
            "common_specifications_applied": [],
            "notified_body": {
                "name": "[If applicable]",
                "id_number": "[If applicable]",
                "certificate_number": "[If applicable]",
            },
            "declaration_statement": (
                f"The AI system '{system.name}' described above is in conformity with the "
                f"requirements of Regulation (EU) 2024/1689 of the European Parliament and of "
                f"the Council on Artificial Intelligence (EU AI Act)."
            ),
            "signatory": {
                "name": "[Authorised signatory name]",
                "title": "[Role/Title]",
                "date": "[Date of signing]",
                "place": "[Place of signing]",
                "signature": "[Signature]",
            },
        },
        "status": "draft",
        "notes": "Complete all fields before signing. This declaration must be updated upon any significant change to the system.",
    }


def generate_fria(system: AiSystem) -> dict:
    """
    Generate Fundamental Rights Impact Assessment (Article 27) structure.
    """
    return {
        "document_type": "fundamental_rights_impact_assessment",
        "article_reference": "Article 27",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_id": str(system.id),
        "content": {
            "1_system_description": {
                "system_name": system.name,
                "version": system.version,
                "provider": system.provider_name or "[Provider]",
                "deployer": "[Your organisation name]",
                "intended_purpose": system.intended_purpose,
                "deployment_context": "[Describe where and how the system will be used]",
                "geographic_scope": "[EU member states where deployed]",
                "deployment_period": "[Start and end dates or 'ongoing']",
            },
            "2_affected_persons": {
                "primary_affected_groups": [
                    "[e.g. Job applicants]",
                    "[e.g. Benefit claimants]",
                    "[e.g. Loan applicants]",
                ],
                "vulnerable_groups": "[Identify particularly vulnerable populations]",
                "estimated_scale": "[Number of persons affected annually]",
            },
            "3_fundamental_rights_assessment": {
                "rights_at_risk": [
                    {
                        "right": "Non-discrimination (Art. 21, EU Charter)",
                        "risk_description": "[How might the system discriminate?]",
                        "likelihood": "medium",
                        "severity": "high",
                        "mitigation": "[Bias auditing, fairness metrics, appeal process]",
                    },
                    {
                        "right": "Human dignity (Art. 1, EU Charter)",
                        "risk_description": "[Could automated decisions undermine dignity?]",
                        "likelihood": "low",
                        "severity": "high",
                        "mitigation": "[Mandatory human review for adverse decisions]",
                    },
                    {
                        "right": "Privacy and data protection (Arts. 7-8, EU Charter)",
                        "risk_description": "[What personal data is processed? Risks?]",
                        "likelihood": "medium",
                        "severity": "medium",
                        "mitigation": "[Data minimisation, DPIA, consent mechanisms]",
                    },
                ],
            },
            "4_mitigation_measures": {
                "technical_measures": [
                    "[e.g. Regular bias audits on model outputs]",
                    "[e.g. Explainability tools for affected persons]",
                ],
                "procedural_measures": [
                    "[e.g. Mandatory human review for high-stakes decisions]",
                    "[e.g. Appeal mechanism within 30 days]",
                ],
                "monitoring": "[How will effectiveness of mitigations be monitored?]",
            },
            "5_consultation": {
                "authorities_consulted": "[Market surveillance authority, DPA if applicable]",
                "consultation_date": "[Date]",
                "feedback_received": "[Summary of feedback]",
                "actions_taken": "[How feedback was incorporated]",
            },
            "6_conclusion": {
                "overall_risk_assessment": "medium",
                "proceed_with_deployment": "[Yes/No/Conditional]",
                "conditions": "[Any conditions or restrictions on deployment]",
                "review_date": "[Date for next FRIA review]",
            },
        },
        "status": "draft",
    }


DOCUMENT_GENERATORS = {
    DocumentType.TECHNICAL_DOCUMENTATION: generate_technical_documentation,
    DocumentType.DECLARATION_OF_CONFORMITY: generate_declaration_of_conformity,
    DocumentType.FRIA: generate_fria,
}
