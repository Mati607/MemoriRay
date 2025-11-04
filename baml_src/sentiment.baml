function SentimentAnalysis(user_message: string) -> string {
  client "GeminiFlashLite"
  prompt #"
    {{ _.role("system") }}
    You are a sentiment analyzer. You will be given a user message and you will need to analyze the sentiment of the user message.
    {{ _.role("user") }}
    {{ user_message }}
  "#
}
