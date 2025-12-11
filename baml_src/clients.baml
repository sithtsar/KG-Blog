// BAML Client Configuration for Google Gemini
// This defines how BAML connects to Google's Gemini API

client<llm> Gemini {
  provider google-ai
  options {
    // Use gemini-2.5-flash-lite from Google AI Studio
    model "gemini-2.5-flash-lite"
    api_key env.GEMINI_API_KEY
  }
}

