import fitz
import re
import streamlit as st


def parse_pdf_to_questions(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parsed_questions = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        q_id_rects = page.search_for("Question ID:")
        if not q_id_rects:
            q_id_rects = page.search_for("Question")

        if not q_id_rects:
            continue

        for i, q_rect in enumerate(q_id_rects):
            y_start = max(0, q_rect.y0 - 10)

            if i + 1 < len(q_id_rects):
                y_next = q_id_rects[i + 1].y0 - 10
            else:
                y_next = page.rect.height

            cut_rects = (
                page.search_for("Answer\n")
                + page.search_for("Answer")
                + page.search_for("Rationale")
                + page.search_for("Correct Answer")
            )

            y_end = y_next
            for c_rect in cut_rects:
                if y_start + 20 < c_rect.y0 <= y_next:
                    y_end = min(y_end, c_rect.y0 - 5)

            clip_rect = fitz.Rect(0, y_start, page.rect.width, y_end)
            pix = page.get_pixmap(clip=clip_rect, dpi=200)
            img_bytes = pix.tobytes("png")

            sub_text = text
            matches = list(re.finditer(r"Question ID:", text, re.IGNORECASE))
            if len(matches) > i:
                start_char = matches[i].start()
                end_char = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                sub_text = text[start_char:end_char]

            options = {}
            opt_pattern = r"(?:^|\n)\s*([A-D])[\.\)]\s*(.*?)(?=\n\s*[A-D][\.\)]|\nRationale|\nCorrect Answer|\nAnswer|$)"
            found_opts = re.findall(opt_pattern, sub_text, re.DOTALL)

            for k, v in found_opts:
                clean_v = v.strip().replace("\n", " ")
                if clean_v:
                    options[k.upper()] = clean_v

            if len(options) < 4:
                options = {
                    "A": "Option A",
                    "B": "Option B",
                    "C": "Option C",
                    "D": "Option D",
                }

            correct_ans = "A"
            ans_match = re.search(
                r"Correct Answer:\s*(?:Choice\s*)?([A-D])", sub_text, re.IGNORECASE
            )
            if ans_match:
                correct_ans = ans_match.group(1).upper()

            parsed_questions.append(
                {
                    "image": img_bytes,
                    "options": options,
                    "correct_answer": correct_ans,
                }
            )

    return parsed_questions


st.set_page_config(page_title="SAT Question Practice", layout="wide")
st.title("Automated PDF Question Engine")

if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "skipped" not in st.session_state:
    st.session_state.skipped = set()

uploaded_file = st.file_uploader("Upload SAT or Practice Test PDF", type=["pdf"])

if uploaded_file and not st.session_state.questions:
    if st.button("Process PDF & Start Quiz"):
        with st.spinner("Processing PDF..."):
            extracted = parse_pdf_to_questions(uploaded_file.read())
            if extracted:
                st.session_state.questions = extracted
                st.session_state.current_q = 0
                st.session_state.user_answers = {}
                st.session_state.skipped = set()
                st.rerun()
            else:
                st.error("No valid questions found in this PDF.")

if st.session_state.questions:
    total = len(st.session_state.questions)
    curr = st.session_state.current_q
    q_data = st.session_state.questions[curr]

    st.sidebar.title("Question Navigator")
    cols = st.sidebar.columns(4)
    for index in range(total):
        col = cols[index % 4]
        label = f"{index + 1}"
        if index in st.session_state.user_answers:
            label = f"[x] {index + 1}"
        elif index in st.session_state.skipped:
            label = f"[-] {index + 1}"

        if col.button(label, key=f"nav_{index}"):
            st.session_state.current_q = index
            st.rerun()

    st.progress((curr + 1) / total)
    st.caption(f"Question {curr + 1} of {total}")

    st.image(q_data["image"], use_container_width=True)

    saved_choice = st.session_state.user_answers.get(curr, "A")

    with st.form(key=f"quiz_form_{curr}"):
        user_choice = st.radio(
            "Select an option:",
            options=list(q_data["options"].keys()),
            index=list(q_data["options"].keys()).index(saved_choice)
            if saved_choice in q_data["options"]
            else 0,
            format_func=lambda x: f"{x.lower()}) {q_data['options'][x]}",
        )

        f_col1, f_col2, f_col3 = st.columns(3)
        submit_btn = f_col1.form_submit_button("Submit Answer")
        skip_btn = f_col2.form_submit_button("Skip Question")
        prev_btn = f_col3.form_submit_button("Previous Question")

    if submit_btn:
        st.session_state.user_answers[curr] = user_choice
        st.session_state.skipped.discard(curr)
        if curr < total - 1:
            st.session_state.current_q += 1
        st.rerun()

    if skip_btn:
        st.session_state.skipped.add(curr)
        if curr < total - 1:
            st.session_state.current_q += 1
        st.rerun()

    if prev_btn:
        if curr > 0:
            st.session_state.current_q -= 1
            st.rerun()

    if curr in st.session_state.user_answers:
        ans = st.session_state.user_answers[curr]
        if ans == q_data["correct_answer"]:
            st.success("Correct!")
        else:
            st.error(f"Incorrect. Correct answer is {q_data['correct_answer'].lower()}.")