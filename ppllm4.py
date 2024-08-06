import streamlit as st
import base64
import requests
import tempfile
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Function to extract text from a PDF file
def extract_text_from_pdf(file):
    pdf_reader = PdfReader(file)
    text = ''
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Function to preprocess extracted text
def preprocess_text(text):
    return ' '.join(text.split())

# Function to split text into chunks (e.g., paragraphs)
def split_text_into_chunks(text, chunk_size=500):
    words = text.split()
    chunks = [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
    return chunks

# Function to match user query with relevant parts of the PDF text
def find_relevant_text(query, text_chunks):
    vectorizer = TfidfVectorizer().fit_transform([query] + text_chunks)
    vectors = vectorizer.toarray()
    cosine_sim = cosine_similarity(vectors)
    similarity_scores = cosine_sim[0][1:]
    most_relevant_index = similarity_scores.argmax()
    return text_chunks[most_relevant_index]

# Function to query Eden AI
def query_edenai_api(api_key, question, context):
    headers = {"Authorization": f"Bearer {api_key}"}
    url = "https://api.edenai.run/v2/text/question_answer"
    payload = {
        "providers": "openai",
        "texts": [context],
        "question": question,
        "examples_context": "In 2017, U.S. life expectancy was 78.6 years.",
        "examples": [["What is human life expectancy in the United States?", "78 years."]],
    }

    response = requests.post(url, json=payload, headers=headers)
    try:
        response.raise_for_status()
        result = response.json()
        st.write(f"Response JSON: {result}")  # Debugging statement
        return result['openai']['answers'][0] if 'openai' in result and 'answers' in result['openai'] else "No content in response."
    except requests.exceptions.HTTPError as http_err:
        error_message = f"HTTP error occurred: {http_err}"
        st.error(error_message)
        st.error(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        error_message = f"Error occurred: {req_err}"
        st.error(error_message)
    except ValueError as json_err:
        error_message = f"JSON decode error: {json_err}"
        st.error(error_message)
        st.error(f"Response content: {response.content}")
    return None

# Function to embed PDF in Streamlit
def display_pdf(file_path):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="800" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

# Streamlit app
st.title("Chat with PDF")

api_key = st.text_input("Enter Eden AI API key:", type="password")
uploaded_files = st.file_uploader("Upload PDF documents", type="pdf", accept_multiple_files=True)

if uploaded_files and api_key:
    if 'pdf_data' not in st.session_state:
        st.session_state.pdf_data = {}

    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state.pdf_data:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(uploaded_file.read())
                temp_file_path = temp_file.name

            pdf_text = extract_text_from_pdf(temp_file_path)
            preprocessed_text = preprocess_text(pdf_text)
            text_chunks = split_text_into_chunks(preprocessed_text)

            st.session_state.pdf_data[uploaded_file.name] = {
                "text_chunks": text_chunks,
                "messages": [{"role": "system", "content": f"Based on the following text, {preprocessed_text}"}],
                "file_path": temp_file_path
            }

    selected_pdf = st.selectbox("Select a PDF to interact with", options=list(st.session_state.pdf_data.keys()))

    if selected_pdf:
        pdf_info = st.session_state.pdf_data[selected_pdf]

        with st.expander("PDF Content", expanded=True):
            display_pdf(pdf_info["file_path"])

        st.write("### Chat History")
        for message in pdf_info["messages"][1:]:  # Skip the initial system message
            if message['role'] == 'user':
                st.write(f"You: {message['content']}")
            else:
                st.write(f"Assistant: {message['content']}")

        user_input = st.text_input("Ask a question about the PDF content:", key=f"user_input_{selected_pdf}")

        if st.button("Send", key=f"send_button_{selected_pdf}"):
            if user_input:
                pdf_info["messages"].append({"role": "user", "content": user_input})

                relevant_text = find_relevant_text(user_input, pdf_info["text_chunks"])
                prompt = f"Based on the following text, {relevant_text}, answer the question: {user_input}"

                response = query_edenai_api(api_key, user_input, relevant_text)
                st.write(f"API Response: {response}")  # Debugging statement
                if response:
                    pdf_info["messages"].append({"role": "assistant", "content": response})
                    st.write(f"Assistant: {response}")
                else:
                    st.write("No response from the API.")

                st.experimental_rerun()
else:
    st.write("Please upload PDF files and enter the API key.")
