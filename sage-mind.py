import os
import json
import streamlit as st
from datetime import datetime
import time
import autogen  # Ensure autogen is installed and available in your PYTHONPATH
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# ---------------------------------------------------
# Custom CSS: Use Helvetica Bold for headings (blue) and Nunito Sans for body text
# ---------------------------------------------------
st.markdown(
    """
    <style>
    /* Headings: Helvetica Bold (or system default bold sans-serif) in blue */
    h1, h2, h3, h4, h5, h6 {
        font-family: Helvetica, sans-serif !important;
        font-weight: bold !important;
        color: #007ACC !important;
    }
    /* Body text: Nunito Sans for readability */
    body, p, span, div, .stMarkdown {
        font-family: 'Nunito Sans', sans-serif !important;
        color: #2C3E50 !important;
    }
    .main-title { font-size: 3.2rem !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------
# OpenAI Client Initialization Using New Style
# ---------------------------------------------------
client = OpenAI()  # Automatically uses OPENAI_API_KEY from .env


def call_openai_chat_completion(messages, model="gpt-4o"):
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7
    )
    return completion


# ---------------------------------------------------
# Classification Mapping: Industry → Domain/Area
# ---------------------------------------------------
industry_to_domain = {
    "Information Technology": "Software development, IT consulting, cloud computing, cybersecurity, data analytics, AI & ML, IT infrastructure",
    "Agriculture, Forestry, Fishing": "Crop production, animal husbandry, forestry, logging, fishing, aquaculture",
    "Mining and Quarrying": "Coal mining, metal ore mining, non-metallic mineral mining, quarrying",
    "Manufacturing": "Food production, beverage manufacturing, textile production, chemical manufacturing, machinery",
    "Electricity, Gas, Water Supply": "Power generation, natural gas distribution, water treatment and supply",
    "Construction": "Residential building, non-residential building, civil engineering, specialized construction",
    "Wholesale and Retail Trade": "Motor vehicle sales, wholesale trade, retail trade",
    "Transportation and Storage": "Land transport, water transport, air transport, warehousing, postal services",
    "Accommodation and Food Services": "Hotels, motels, restaurants, catering services",
    "Information and Communication": "Publishing, motion picture production, broadcasting, telecommunications, IT services",
    "Financial and Insurance Activities": "Banking, insurance, pension funding, financial leasing, investment services",
    "Real Estate Activities": "Real estate development, property management, real estate appraisal",
    "Professional, Scientific, Technical Activities": "Legal services, accounting, management consulting, architectural services, scientific research",
    "Administrative and Support Services": "Rental services, employment services, travel agencies, security services",
    "Public Administration and Defense": "Governmental activities, defense activities, public order and safety",
    "Education": "Primary education, secondary education, higher education, vocational training",
    "Human Health and Social Work Activities": "Hospital activities, medical practice, dental practice, residential care, social work",
    "Arts, Entertainment, Recreation": "Creative arts, libraries, archives, museums, gambling, sports activities",
    "Other Service Activities": "Membership organizations, repair of personal goods, personal services"
}
default_industry = "Information Technology"

# ---------------------------------------------------
# Autogen Agent Definitions with Detailed Prompts
# ---------------------------------------------------
llm_config = {
    "model": "gpt-4o",
    "api_key": os.getenv("OPENAI_API_KEY"),
}

# Research Agent: Retrieves focused information strictly about the user-entered topic.
research_agent = autogen.AssistantAgent(
    name="DomainResearcher",
    llm_config=llm_config,
    system_message="""
You are an expert researcher with impeccable focus and strong chain-of-thought reasoning.
The user has provided a specific topic along with classification details (Industry and Domain/Area).
Your task is to retrieve the latest, high-quality information strictly relevant to the user-entered topic.
For example, if the topic is "Machine Learning," focus solely on machine learning algorithms, techniques (supervised, unsupervised, reinforcement learning, etc.), case studies, and related data.
Do not include unrelated content (such as generative AI) unless explicitly requested.
Structure your answer with clear section headers, detailed bullet points, tables, and concrete examples.
Include working, clickable reference URLs from reputable sources.
Explain your reasoning step-by-step.
    """
)


# Ensemble Content Agent: Synthesizes research data into a structured report.
class EnsembleContentAgent(autogen.AssistantAgent):
    def process(self, message):
        result = call_openai_chat_completion([{"role": "user", "content": message}])
        return result["choices"][0]["message"]["content"]


ensemble_agent = EnsembleContentAgent(
    name="EnsembleSynthesizer",
    llm_config=llm_config,
    system_message="""
You are a content synthesizer with advanced chain-of-thought capabilities.
Using the research data and the classification details (Industry and Domain/Area), synthesize a comprehensive learning report in markdown that is strictly focused on the user-entered topic.
Your report MUST include the following sections:
  - **Introduction:** Provide context and an overview.
  - **Key Concepts:** Detail the core ideas and methodologies.
  - **Real-World Applications:** Provide examples and case studies.
  - **Challenges:** Discuss obstacles or limitations.
  - **Future Trends:** Explore potential innovations.
  - **Conclusion:** Summarize the report and include a polite follow-up invitation: "Would you like to explore follow-up topics on this subject?"
Include detailed bullet points, tables (if applicable), specific examples, and working, clickable reference URLs in each section.
Return only a valid markdown document and append TERMINATE at the end.
    """
)

# Writer Agent: Finalizes and formats the report.
writer_agent = autogen.AssistantAgent(
    name="Writer",
    llm_config=llm_config,
    system_message="""
You are a professional writer specializing in educational content.
Refine and format the synthesized report into a final, polished markdown document.
Ensure that the final output includes:
  - Clearly formatted section headers and sub-headers.
  - Detailed descriptions, explanatory paragraphs, bullet points, tables, and concrete examples strictly focused on the user-entered topic.
  - Embedded, working reference URLs.
  - A concluding section summarizing the report and inviting further exploration: "Would you like to explore follow-up topics on this subject?"
Output only the final report in markdown without any extra commentary.
    """
)

# Quiz Agent: Generates a multiple-choice quiz.
quiz_agent = autogen.AssistantAgent(
    name="QuizGenerator",
    llm_config=llm_config,
    system_message="""
You are an expert quiz generator.
Based on the user-entered topic and the detailed learning report generated, create a multiple-choice quiz with {num_questions} questions.
Each question must have 4 options and clearly indicate the correct answer.
Ensure that the quiz questions are directly relevant to the learning content.
Use a friendly tone. Append TERMINATE at the end.
    """
)

# Critic Agent: Performs peer review on the final report.
critic_agent = autogen.AssistantAgent(
    name="Critic",
    is_termination_msg=lambda x: x.get("content", "").find("TERMINATE") >= 0,
    llm_config=llm_config,
    system_message="""
You are a meticulous critic with strong analytical and chain-of-thought reasoning.
Review the final learning report thoroughly and provide concise, constructive feedback using bullet points.
Ensure that the content remains strictly on the user-entered topic and includes accurate, working reference URLs.
    """
)

legal_reviewer = autogen.AssistantAgent(
    name="LegalReviewer",
    llm_config=llm_config,
    system_message="You are a legal reviewer. Provide up to 3 concise bullet points ensuring legal compliance and clarity."
)

consistency_reviewer = autogen.AssistantAgent(
    name="ConsistencyReviewer",
    llm_config=llm_config,
    system_message="You are a consistency reviewer. Verify that the report is coherent and that all data and URLs are consistent. Provide up to 3 bullet points."
)

text_alignment_reviewer = autogen.AssistantAgent(
    name="TextAlignmentReviewer",
    llm_config=llm_config,
    system_message="You are a text alignment reviewer. Ensure that all numerical data and explanations are clearly aligned. Provide up to 3 bullet points."
)

completion_reviewer = autogen.AssistantAgent(
    name="CompletionReviewer",
    llm_config=llm_config,
    system_message="You are a completion reviewer. Confirm that the report includes all required sections (Introduction, Key Concepts, Real-World Applications, Challenges, Future Trends, Conclusion with follow-up invitation). Provide up to 3 bullet points."
)

meta_reviewer = autogen.AssistantAgent(
    name="MetaReviewer",
    llm_config=llm_config,
    system_message="You are a meta reviewer. Aggregate feedback from all reviewers and provide final improvement suggestions."
)


def reflection_message(recipient, messages, sender, config):
    return f"Review the following content: {recipient.chat_messages_for_summary(sender)[-1]['content']}"


review_chats = [
    {"recipient": legal_reviewer,
     "message": reflection_message,
     "summary_method": "reflection_with_llm",
     "summary_args": {"summary_prompt": "Return review as JSON with keys 'Reviewer' and 'Review'."},
     "max_turns": 1},
    {"recipient": text_alignment_reviewer,
     "message": reflection_message,
     "summary_method": "reflection_with_llm",
     "summary_args": {"summary_prompt": "Return review as JSON with keys 'reviewer' and 'review'."},
     "max_turns": 1},
    {"recipient": consistency_reviewer,
     "message": reflection_message,
     "summary_method": "reflection_with_llm",
     "summary_args": {"summary_prompt": "Return review as JSON with keys 'reviewer' and 'review'."},
     "max_turns": 1},
    {"recipient": completion_reviewer,
     "message": reflection_message,
     "summary_method": "reflection_with_llm",
     "summary_args": {"summary_prompt": "Return review as JSON with keys 'reviewer' and 'review'."},
     "max_turns": 1},
    {"recipient": meta_reviewer,
     "message": "Aggregate feedback from all reviewers and provide final suggestions on the content.",
     "max_turns": 1},
]
critic_agent.register_nested_chats(review_chats, trigger=writer_agent)

# User Proxy Agent: Simulates user input and orchestrates feedback.
user_proxy_auto = autogen.UserProxyAgent(
    name="UserProxyAuto",
    human_input_mode="NEVER",
    is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
    code_execution_config={"last_n_messages": 3, "work_dir": "coding", "use_docker": False},
)

# ---------------------------------------------------
# Streamlit UI & Orchestration with Enhanced Widgets, Detailed Phase Messages, and Quiz Generation
# ---------------------------------------------------

# Sidebar: Header and info.
st.sidebar.header("Sage-Mind")
st.sidebar.subheader("Adaptive Learning Tutor – Powered by Agentic AI")
st.sidebar.info("An Advanced Multi-Agent Adaptive-Learning App")

# Sidebar: Classification – Industry and Domain/Area.
st.sidebar.subheader("Classification")
industry_options = list(industry_to_domain.keys())
selected_industry = st.sidebar.selectbox("Industry", industry_options, index=industry_options.index(default_industry))
selected_domain_area = industry_to_domain.get(selected_industry, "N/A")
st.sidebar.markdown(f"**Domain/Area:** {selected_domain_area}")

# Sidebar: Advanced Settings expander with Learning Mode.
with st.sidebar.expander("Advanced Settings", expanded=True):
    learning_mode = st.radio("Learning Mode", ["Binge Reading", "Working and Learning", "Immersive Learning"])
    # (An advanced settings agent can be integrated here if needed.)

# Main area: Title and input form.
st.title("Sage Mind – Adaptive Self-Learning Tutor")
st.markdown("<h2 class='sub-title'>Enter the topic you want to learn</h2>", unsafe_allow_html=True)

with st.form(key="learning_form"):
    topic_prompt = st.text_area("Topic", placeholder="Enter the topic you want to learn...")
    feedback_text = st.text_input("Optional Feedback",
                                  placeholder="e.g., 'more detailed', 'more concise', 'restructure'")
    submit_button = st.form_submit_button(label="Learn Now")

# Additional Feature: Quiz Generation
st.markdown("### Generate Quiz")
quiz_num = st.slider("Select number of quiz questions", min_value=1, max_value=20, value=5, step=1)
if st.button("Generate Quiz"):
    quiz_task = (
        f"Based on the topic '{topic_prompt}' and the generated learning report, create a multiple-choice quiz with {quiz_num} questions. "
        "Each question must have 4 options and clearly indicate the correct answer. Use a friendly tone. Append TERMINATE when complete."
    )
    with st.spinner("Generating quiz..."):
        quiz_results = autogen.initiate_chats([
            {
                "sender": user_proxy_auto,
                "recipient": quiz_agent,
                "message": quiz_task,
                "silent": False,
                "summary_method": "reflection_with_llm",
                "summary_args": {"summary_prompt": "Return the generated quiz as markdown."},
                "clear_history": False,
                "carryover": "Append TERMINATE when complete."
            }
        ])
    st.markdown("### Quiz")
    st.markdown(quiz_results[-1].chat_history[-1]["content"])

if submit_button:
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Build the research task.
    research_task = (
        f"Today is {date_str}. Research the topic: '{topic_prompt}' with the following classification:\n"
        f"Industry: '{selected_industry}'\n"
        f"Domain/Area: '{selected_domain_area}'\n\n"
        "Focus on gathering the latest, high-quality information strictly relevant to the user-entered topic. "
        "Use a detailed chain-of-thought approach to produce an answer with clear section headers, detailed bullet points, tables, and examples. "
        "Include working, clickable reference URLs from reputable sources. Tailor your output for the selected Learning Mode: "
        f"'{learning_mode}'."
    )

    synthesis_task = (
        "Using the gathered research data, synthesize a comprehensive learning report in markdown that includes the following sections:\n"
        "- **Introduction:** A detailed introduction providing context about the topic.\n"
        "- **Key Concepts:** Outline the core ideas and methodologies relevant to the topic.\n"
        "- **Real-World Applications:** Provide examples and case studies demonstrating practical applications.\n"
        "- **Challenges and Limitations:** Discuss any obstacles or limitations related to the topic.\n"
        "- **Future Trends:** Explore upcoming developments and innovations.\n"
        "- **Conclusion:** Summarize the report and end with a polite invitation: \"Would you like to explore follow-up topics on this subject?\"\n"
        "Return your output as a markdown document (not JSON) that is well structured and clearly separates each section. "
        "Ensure that the content is engaging, factually grounded, and reflects thorough chain-of-thought reasoning. Append TERMINATE when complete."
    )

    # Phase-wise progress with detailed dynamic messages.
    progress_bar = st.progress(0)
    status_text = st.empty()

    status_text.info("Phase 1: Researching the topic and gathering precise data...")
    progress_bar.progress(30)
    time.sleep(2)

    with st.spinner("Phase 2: Peer review underway – validating data and cross-checking references..."):
        # Run the research and synthesis in a combined call sequence.
        chat_results = autogen.initiate_chats([
            {
                "sender": user_proxy_auto,
                "recipient": research_agent,
                "message": research_task,
                "silent": False,
                "summary_method": "reflection_with_llm",
                "summary_args": {"summary_prompt": "Return the gathered research data with key references."},
                "clear_history": False,
                "carryover": "Append TERMINATE when done."
            },
            {
                "sender": user_proxy_auto,
                "recipient": ensemble_agent,
                "message": synthesis_task,
                "silent": False,
                "summary_method": "reflection_with_llm",
                "summary_args": {"summary_prompt": "Return the synthesized report in markdown."},
                "clear_history": False,
                "carryover": "Append TERMINATE when complete."
            },
            {
                "sender": critic_agent,
                "recipient": writer_agent,
                "message": "Using the synthesized draft, develop a final refined report in markdown. Append TERMINATE when complete.",
                "carryover": "Ensure the final report includes detailed sections, figures, tables, commentary, and a concluding invitation for follow-up topics.",
                "max_turns": 2,
                "summary_method": "last_msg",
            }
        ])
    progress_bar.progress(90)
    status_text.success("Phase 3: Finalizing the report – compiling the final document...")
    time.sleep(1)
    progress_bar.progress(100)
    st.balloons()

    # Display the final learning report as raw markdown.
    final_report = chat_results[-1].chat_history[-1]["content"].replace("TERMINATE", "").strip()
    st.markdown("### Learning Content")
    st.markdown(final_report)

    # Process optional feedback.
    if feedback_text.strip():
        with st.spinner("Incorporating your feedback and refining the report..."):
            feedback_result = autogen.initiate_chats([
                {
                    "sender": user_proxy_auto,
                    "recipient": critic_agent,
                    "message": f"User feedback: {feedback_text}. Please adjust the content accordingly. Append TERMINATE when done.",
                    "silent": False,
                    "summary_method": "reflection_with_llm",
                    "summary_args": {"summary_prompt": "Return updated feedback."},
                    "clear_history": False,
                    "carryover": "Re-run synthesis immediately with the provided feedback."
                }
            ])
            st.markdown(feedback_result[-1].chat_history[-1]["content"])
