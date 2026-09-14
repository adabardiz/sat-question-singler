import fitz
import re
import streamlit as st


def parse_pdf_to_questions(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parsed_questions = []

    for page in doc:
        text = page.get_text("text")
        q_matches = list(
            re.finditer(r"Question ID:\s*([a-f0-9]+)", text, re.IGNORECASE)
        )

        if q_matches:
            q_rects = page.search_for("Question ID:")
            for i, q_rect in enumerate(q_rects):
                y_start = max(0, q_rect.y0 - 5)

                if i + 1 < len(q_rects):
                    y_next = q_rects[i + 1].y0 - 5
                else:
                    y_next = page.rect.height

                start_pos = q_matches[i].start()
                end_pos = (
                    q_matches[i + 1].start()
                    if i + 1 < len(q_matches)
                    else len(text)
                )
                q_text = text[start_pos:end_pos]

                options = {}
                opt_matches = re.findall(
                    r"(?:^|\n)\s*([A-D])[\.\)]\s*(.*?)(?=\n\s*[A-D][\.\)]|\nRationale|\nCorrect Answer|\nQuestion ID|$)",
                    q_text,
                    re.DOTALL,
                )
                for k, v in opt_matches:
                    options[k.upper()] = v.strip().replace("\n", " ")

                opt_a_rects = (
                    page.search_for("A.")
                    or page.search_for("A)")
                    or page.search_for("A ")
                )
                y_end = y_next
                for opt_rect in opt_a_rects:
                    if y_start < opt_rect.y0 < y_next:
                        y_end = opt_rect.y0 - 5
                        break

                clip_rect = fitz.Rect(0, y_start, page.rect.width, y_end)
                pix = page.get_pixmap(clip=clip_rect, dpi=180)
                img_bytes = pix.tobytes("png")

                if len(options) < 4:
                    options = {
                        "A": "Option A",
                        "B": "Option B",
                        "C": "Option C",
                        "D": "Option D",
                    }

                correct_ans = "A"
                ans_match = re.search(
                    r"Correct Answer[:\s]*([A-D])", q_text, re.IGNORECASE
                )
                if ans_match:
                    correct_ans = ans_match.group(1).upper()

                parsed_questions.append(
                    {
                        "image": img_bytes,
                        "options": options,
                        "correct_answer": correct_ans,
                        "explanation": "Review the problem steps carefully.",
                    }
                )
        else:
            if re.search(r"[A-D][\.\)]", text):
                options = {}
                opt_matches = re.findall(
                    r"(?:^|\n)\s*([A-D])[\.\)]\s*(.*?)(?=\n\s*[A-D][\.\)]|\nRationale|\nCorrect Answer|$)",
                    text,
                    re.DOTALL,
                )
                for k, v in opt_matches:
                    options[k.upper()] = v.strip().replace("\n", " ")

                opt_a_rects = (
                    page.search_for("A.")
                    or page.search_for("A)")
                    or page.search_for("A ")
                )
                y_end = page.rect.height
                if opt_a_rects:
                    y_end = opt_a_rects[0].y0 - 5

                clip_rect = fitz.Rect(0, 0, page.rect.width, y_end)
                pix = page.get_pixmap(clip=clip_rect, dpi=180)
                img_bytes = pix.tobytes("png")

                if len(options) < 4:
                    options = {
                        "A": "Option A",
                        "B": "Option B",
                        "C": "Option C",
                        "D": "Option D",
                    }

                parsed_questions.append(
                    {
                        "image": img_bytes,
                        "options": options,
                        "correct_answer": "A",
                        "explanation": "Review the problem steps carefully.",
                    }
                )

    return parsed_questions


st.set_page_config(page_title="PDF SAT Practice", page_icon="📝")
st.title("Automated PDF Question Engine")

if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "score" not in st.session_state:
    st.session_state.score = 0
if "answered" not in st.session_state:
    st.session_state.answered = False

uploaded_file = st.file_uploader(
    "Upload SAT or Practice Test PDF", type=["pdf"]
)

if uploaded_file and not st.session_state.questions:
    if st.button("Process PDF & Start Quiz"):
        with st.spinner("Clipping questions from PDF..."):
            extracted = parse_pdf_to_questions(uploaded_file.read())
            if extracted:
                st.session_state.questions = extracted
                st.session_state.current_q = 0
                st.session_state.score = 0
                st.rerun()
            else:
                st.error(
                    "Could not isolate questions. Make sure the PDF contains valid question formats."
                )

if st.session_state.questions:
    total_q = len(st.session_state.questions)
    curr_idx = st.session_state.current_q
    q_data = st.session_state.questions[curr_idx]

    st.progress((curr_idx + 1) / total_q)
    st.caption(f"Question {curr_idx + 1} of {total_q}")

    st.image(q_data["image"], use_container_width=True)

    with st.form(key=f"quiz_form_{curr_idx}"):
        user_choice = st.radio(
            "Select an option:",
            options=list(q_data["options"].keys()),
            format_func=lambda x: f"{x.lower()}) {q_data['options'][x]}",
        )
        submit = st.form_submit_button("Submit Answer")

    if submit:
        st.session_state.answered = True
        if user_choice == q_data["correct_answer"]:
            st.success("Correct!")
            st.session_state.score += 1
        else:
            st.error(f"Incorrect. Your choice: {user_choice}")

        st.info(f"**Explanation:** {q_data['explanation']}")

    if st.session_state.answered:
        if curr_idx < total_q - 1:
            if st.button("Next Question"):
                st.session_state.current_q += 1
                st.session_state.answered = False
                st.rerun()
        else:
            st.balloons()
            st.success(
                f"Practice Complete! Final Score: {st.session_state.score}/{total_q}"
            )
            if st.button("Upload Another Test"):
                st.session_state.questions = []
                st.session_state.current_q = 0
                st.session_state.answered = False
                st.rerun()