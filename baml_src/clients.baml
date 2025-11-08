client<llm> GeminiDefault {
  provider google-ai
  options {
    model "gemini-2.5-flash"
  }
}

client<llm> GeminiFlashLite {
  provider google-ai
  options {
    model "gemini-2.0-flash"
  }
}

client<llm> GeminiFlashImage {
  provider google-ai
  options {
    model "gemini-2.0-flash-lite"
  }
}

client<llm> GeminiImageSelector {
  provider google-ai
  options {
    model "gemini-2.5-flash-lite"
  }
}
