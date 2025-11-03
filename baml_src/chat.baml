function ChatReply(message: string) -> string {
  client "GeminiDefault"
  prompt #"
    You are a helpful assistant.
    {{ ctx.output_format }}

    USER:
    {{ message }}
  "#
}
