import os
import requests
import streamlit as st

CHATBOT_URL = os.getenv("CHATBOT_URL", "http://localhost:8000/bank-rag-agent") # change port 8081 to 8000
RESET_URL = CHATBOT_URL.replace("/bank-rag-agent", "/reset-conversation")

# ---- Session State Setup ---- 
if "role" not in st.session_state:
    st.session_state.role = None
if "verified" not in st.session_state:
    st.session_state.verified = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "customer_name" not in st.session_state:
    st.session_state.customer_name = ""
if "customer_id" not in st.session_state:  #  NEW: store verified user's ID
    st.session_state.customer_id = None

# ---- Sidebar ----
with st.sidebar:
    st.header("About")
    st.markdown("""
        This chatbot interfaces with a
        [LangChain](https://python.langchain.com/docs/get_started/introduction)
        agent designed to answer questions about the customers, their mortgages,
        payment due dates, payments and fees in a dummy banking system.
        The agent uses retrieval-augment generation (RAG) over both
        structured and unstructured data that has been synthetically generated.
    """)

    st.header("Example Questions")
    st.markdown("""- What is the current due amount on my mortgage""")
    st.markdown("""- What is the current wait time at wallace-hamilton branch?""")
    st.markdown("""- Are there any late fees on my mortgage""")
    st.markdown("- How to avoid getting charged late fees?")
    st.markdown("- What are the terms and conditions for the new mortgage product?")
    st.markdown("- What was the total late fee charged for customer Bob?")
    st.markdown("- How many active 'Adjustable-Rate' loans are held by customers in New York?")

# ---- Title ---- 
st.title("Banking System Chatbot")

# ---- Role Selection ---- 
st.session_state.role = st.selectbox("Please select your role:", ["", "Customer", "Banker"])

# --- CUSTOMER VERIFICATION FLOW ---
if st.session_state.role == "Customer" and not st.session_state.verified:
    st.subheader("Customer Verification")

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    zip_code = st.text_input("Zip Code")
    phone = st.text_input("Phone Number")

    if st.button("Verify"):
        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "zip_code": zip_code,
            "phone": phone
        }
        try:
            # change hardcode url 
            verify_url = CHATBOT_URL.replace("/bank-rag-agent", "/verify-customer")
            res = requests.post(verify_url, json=payload)


            # store response.json() in a variable ONCE
            res_data = res.json()
            print("✅ Backend verify response:", res_data)  # ✅ DEBUG

            if res.status_code == 200 and res_data.get("verified"):
                st.session_state.verified = True
                st.session_state.customer_name = f"{first_name} {last_name}"
                st.session_state.customer_id = res_data.get("customer_id")  # ✅ NEW: Store customer ID
                st.success("✅ Verification successful!")

                st.markdown(f"Verified Customer ID:  `{st.session_state.customer_id}`") ## can comment this out later


            else:
                st.error("❌ Verification failed. Please check your information.")
        except Exception as e:
            st.error(f"⚠️ Error during verification: {e}")

# ---- Welcome Message ----
if st.session_state.role == "Banker":
    st.success("👋 Welcome Banker! You may now ask your question.")

if st.session_state.role == "Customer" and st.session_state.verified:
    st.success(f"👋 Welcome back, **{st.session_state.customer_name}**! You may now ask your question.")
    # st.markdown(f"🆔 (Debug) Customer ID in session: `{st.session_state.customer_id}`")

# ---- Reset Button ----
if st.session_state.role in ["Banker", "Customer"]:
    if st.button("🔁 Reset Conversation"):
        payload = {"role": st.session_state.role, "customer_id": st.session_state.customer_id}
        try:
            res = requests.post(RESET_URL, params=payload)
            if res.status_code == 200:
                st.session_state.messages = []
                st.success("✅ Conversation reset!")
            else:
                st.error("❌ Reset failed. Please try again.")
        except Exception as e:
            st.error(f"⚠️ Error during reset: {e}")


# ---- Info Prompt ----
st.info("Ask me questions about product, promotions, bank branches, transactions, fees, payments, FAQs, and appointment times!")

# ---- Chat Interface ----
if st.session_state.role == "Banker" or (st.session_state.role == "Customer" and st.session_state.verified):

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if "output" in message:
                st.markdown(message["output"])
            if "explanation" in message:
                with st.status("How was this generated", state="complete"):
                    st.info(message["explanation"])

    if prompt := st.chat_input("What do you want to know?"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "output": prompt})

        # ✅ NEW: Always include customer_id (None if banker)
        data = {
            "input": prompt,
            "customer_id": st.session_state.customer_id,
            "role": st.session_state.role  # <-- Add this
        }

        print(" Sending payload to backend:", data)


        with st.spinner("Searching for an answer..."):
            response = requests.post(CHATBOT_URL, json=data)
            if response.status_code == 200:
                output_text = response.json()["output"]
                explanation = response.json()["intermediate_steps"]
            else:
                output_text = "An error occurred. Please try again later."
                explanation = output_text

        st.chat_message("assistant").markdown(output_text)
        st.status("How was this generated?", state="complete").info(explanation)
        st.session_state.messages.append({
            "role": "assistant",
            "output": output_text,
            "explanation": explanation
        })
