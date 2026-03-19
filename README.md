## 📌 Agentic-AI Loan Approval Chatbot

## 📖 Overview

An agentic AI-powered loan sales assistant that simulates a human BFSI sales executive. Built on a Master Agent + Worker Agents architecture, the system uses Groq's LLaMA 70B with OpenAI-compatible tool-calling to drive an autonomous conversational loop — the LLM decides when to verify identity, run credit checks, and generate sanction letters, without any hardcoded sequencing.The system handles emotion-aware dialogue, hesitation management, consent-based EMI disclosure, real-time KYC lookup, deterministic underwriting, and personalised PDF sanction letter generation - end to end, entirely through chat.

## 🧠 Key Features
#### True Agentic Orchestration:
LLM drives the workflow via tool-calling; no if/else state machine. The Master Agent reasons about conversation context and autonomously sequences KYC → Underwriting → Sanction Letter generation
#### Emotion-Aware Conversation:
Detects hesitation, financial anxiety, and first-time borrower concerns; responds with empathy and product education before collecting any data
#### Real KYC Verification :
DynamoDB CRM lookup returning verified customer profile including credit score, pre-approved limit, and salary
#### Deterministic Underwriting Engine:
Rule-based credit eligibility with dynamic interest rates (11.5–13.5% p.a.) based on credit score, EMI affordability checks, and salary slip verification flow for borderline cases
#### Personalised PDF Sanction Letters:
Generated per customer using fpdf2, uploaded to S3, delivered via presigned URL
#### Persistent Session Memory:
Full conversation state stored in DynamoDB; survives Lambda cold starts and redeployments
#### API Key Rotation:
Mltiple Groq keys rotated automatically to handle free-tier rate limits without service interruption
#### Constrained Agency Design:
LLM handles judgment and empathy; deterministic code handles compliance and outcomes — the right balance for regulated BFSI environments

## 🏗️ System Architecture
![System Architecture Diagram](Architecture.jpeg)

## Landing Page
<img width="1833" height="880" alt="image" src="https://github.com/user-attachments/assets/44e72244-545f-431e-b03a-427ee4d1a5b6" />


## 🧪 Experiments
The system was tested across multiple real-world loan scenarios including instant approvals, borderline cases requiring salary slip verification, and rejections due to low credit scores. Each scenario was run across all 10 synthetic customer profiles to validate the full decision matrix. Conversation quality was evaluated on naturalness, empathy handling, and correct tool-call sequencing. Edge cases tested include hesitant customers, mid-conversation amount changes, and multi-turn clarification flows.

## 📌 Future Improvements
- Real KYC & Credit Bureau Integration — replace mock DynamoDB lookups with live UIDAI, CKYC, and CIBIL/Experian API calls for production-grade identity and credit verification
- Persistent Customer Memory — link sessions to verified customer identity so returning customers are recognised across conversations
- Document Upload UI — replace the simulated salary slip flow with an actual in-chat file upload experience using S3 presigned PUT URLs
- Multi-language Support — extend Tia to converse in Hindi, Tamil, Telugu and other regional languages using LLaMA's multilingual capabilities
- Reinforcement Learning from Human Feedback — fine-tune the conversation model on real advisor-customer transcripts to improve sales conversion rates
- Analytics Dashboard — track drop-off points, approval rates, and conversation quality metrics to continuously improve the funnel
