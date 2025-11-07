client<llm> GeminiDefault {
  provider google-ai
  options {
    model "gemini-2.5-flash"
  }
}

client<llm> GeminiFlashLite {
  provider google-ai
  options {
    model "gemini-2.0-flash-lite"
  }
}

