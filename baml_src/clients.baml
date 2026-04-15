client<llm> GeminiDefault {
  provider google-ai
  options {
    model "gemini-2.5-flash"
  }
}

// Longer timeouts: full HTML reports can exceed the default LLM deadline.
client<llm> GeminiReportHtml {
  provider google-ai
  options {
    model "gemini-2.5-flash"
    http {
      connect_timeout_ms 20000
      request_timeout_ms 300000
    }
  }
}

client<llm> GeminiFlashLite {
  provider google-ai
  options {
    model "gemini-2.5-flash"
  }
}

client<llm> GeminiFlashImage {
  provider google-ai
  options {
    model "gemini-2.5-flash"
  }
}

client<llm> GeminiImageSelector {
  provider google-ai
  options {
    model "gemini-2.5-flash"
  }
}
