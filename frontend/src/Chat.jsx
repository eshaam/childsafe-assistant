import { useState, useEffect, useRef } from "react";
import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/query";

const examplePrompts = [
  {
    id: 1,
    text: "Who is ChildSafe South Africa?",
    icon: "🏢",
    gradient: "from-purple-500 to-pink-500",
    description: "Learn about the organization"
  },
  {
    id: 2,
    text: "Show me articles from around the web on ChildSafe South Africa",
    icon: "🌐",
    gradient: "from-blue-500 to-cyan-500",
    description: "Latest web articles and news"
  },
  {
    id: 3,
    text: "Compare the latest financial performance with the previous years",
    icon: "📊",
    gradient: "from-green-500 to-emerald-500",
    description: "Financial analysis and trends"
  }
];

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showExamples, setShowExamples] = useState(true);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
    // Hide main examples when messages exist, but keep toggle working
  }, [messages]);

  const handleExampleClick = (promptText) => {
    setInput(promptText);
    // Auto-send the message after a short delay
    setTimeout(() => {
      sendMessage(promptText);
    }, 100);
  };

  const sendMessage = async (queryText = null) => {
    const messageToSend = queryText || input;
    if (!messageToSend.trim()) return;

    const userMsg = { role: "user", content: messageToSend };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    setInput("");

    try {
      const res = await axios.post(API_URL, { query: messageToSend });
      const response = res.data.results;

      // Format the response nicely for the new langchain RAG format
      let formattedContent = "";

      if (response.error) {
        formattedContent = `Error: ${response.error}`;
      } else if (response.answer) {
        // New format: smart_query with Gemini
        formattedContent = `${response.answer}`;

        // Add web sources if available
        if (response.articles && response.articles.length > 0) {
          formattedContent += "\n\n---\n\n**Web Sources:**\n";
          response.articles.forEach((article) => {
            const title = article.title || "Untitled";
            const url = article.link || article.url || "#";
            const snippet = article.snippet || article.content || "";
            formattedContent += `\n- [${title}](${url})${snippet ? `\n   ${snippet.substring(0, 100)}...` : ''}`;
          });
        }

        // Add local document sources if available
        if (response.metadatas && response.metadatas.length > 0) {
          formattedContent += "\n\n---\n\n**Report Sources:**\n";
          response.metadatas.forEach((meta) => {
            const source = meta.report_year || meta.source || "Unknown source";
            const page = meta.page || "?";
            formattedContent += `\n- ${source} (Page ${page})`;
          });
        }

        // Add query rewriting info
        if (response.rewritten && response.rewritten !== input) {
          formattedContent += `\n\n---\n\n*Query refined to: "${response.rewritten}"*`;
        }
      } else {
        formattedContent = "I couldn't find any relevant information. Please try rephrasing your question.";
      }

      const botMsg = {
        role: "bot",
        content: formattedContent,
        mode: response.mode || "unknown"
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      const errMsg = { role: "bot", content: "Error querying API: " + err.message };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatMessage = (content) => {
    // Simple markdown-like formatting
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:text-blue-800 underline">$1</a>')
      .replace(/---/g, '<hr class="my-4 border-gray-300">')
      .replace(/\n\n/g, '</p><p class="mb-2">')
      .replace(/\n/g, '<br>');
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div className="border-b border-gray-100 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-[#a5cd39] rounded-lg">
                <span className="text-white font-bold text-lg">C</span>
              </div>
              <div>
                <h1 className="text-xl font-semibold text-[#a5cd39]">ChildSafe South Africa Assistant</h1>
                <p className="text-sm text-gray-500">Chat with annual reports and news</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Chat Container */}
      <div className="max-w-3xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {messages.length === 0 && (
          <div className="text-center mb-12">
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-[#a5cd39] mb-6">
              Welcome to ChildSafe South Africa Assistant
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
              Ask me about ChildSafe's annual reports or search for articles from around the web. I'll help you find the information you need.
            </p>

            {/* Example Prompts */}
            <div className="max-w-4xl mx-auto">
              <h3 className="text-lg font-semibold text-gray-700 mb-6">Try these examples:</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                {examplePrompts.map((prompt) => (
                  <button
                    key={prompt.id}
                    onClick={() => handleExampleClick(prompt.text)}
                    className={`group relative overflow-hidden rounded-2xl p-6 text-left transition-all duration-300 transform hover:scale-105 hover:shadow-lg bg-gradient-to-br ${prompt.gradient} hover:shadow-xl border border-white/20 backdrop-blur-sm`}
                  >
                    {/* Background Pattern */}
                    <div className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-20 transition-opacity duration-300"></div>

                    {/* Content */}
                    <div className="relative z-10">
                      <div className="flex items-center mb-3">
                        <span className="text-2xl mr-3">{prompt.icon}</span>
                        <div className="w-2 h-2 bg-white/60 rounded-full animate-pulse"></div>
                      </div>
                      <h4 className="text-white font-semibold text-lg mb-2 leading-tight">
                        {prompt.text}
                      </h4>
                      <p className="text-white/80 text-sm leading-relaxed">
                        {prompt.description}
                      </p>
                    </div>

                    {/* Hover Effect */}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>

                    {/* Click Indicator */}
                    <div className="absolute bottom-4 right-4">
                      <svg className="w-5 h-5 text-white/60 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.length > 0 && (
          <div className="space-y-6 mb-8">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div className={`max-w-[80%] rounded-xl p-5 border ${msg.role === "user"
                  ? "bg-[#a5cd39]/20 border-[#a5cd39]/30 text-gray-800"
                  : "bg-white border-gray-200 text-gray-700 shadow-sm"
                  }`}>
                  {msg.role === "bot" && msg.mode && (
                    <div className="mb-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        msg.mode === "local"
                          ? "bg-green-100 text-green-800"
                          : "bg-blue-100 text-blue-800"
                      }`}>
                        {msg.mode === "local" ? "📚 Answer from Reports" : "🌐 Answer from Web"}
                      </span>
                    </div>
                  )}
                  <div
                    className="text-base leading-relaxed whitespace-pre-wrap"
                    dangerouslySetInnerHTML={{
                      __html: msg.role === "bot"
                        ? formatMessage(msg.content)
                        : msg.content.replace(/\n/g, '<br>')
                    }}
                  />
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="max-w-[80%] bg-white rounded-xl p-5 shadow-sm border border-gray-200">
                  <h3 className="font-medium text-[#a5cd39]">Thinking...</h3>
                  <div className="flex space-x-1 mt-2">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200"></div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input Area */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-lg">
          <div className="p-6">
            <div className="flex items-end space-x-3">
              <div className="flex-1">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask about ChildSafe annual reports or search for articles..."
                  className="w-full bg-white text-gray-900 rounded-xl px-6 py-4 pr-16 resize-none focus:outline-none focus:ring-2 focus:ring-[#a5cd39] placeholder-gray-400 text-base border border-gray-200"
                  rows={1}
                  style={{ minHeight: '52px', maxHeight: '140px' }}
                />
              </div>
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className={`px-6 py-4 rounded-xl font-medium transition-all ${loading || !input.trim()
                  ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                  : "bg-[#a5cd39] text-white hover:bg-[#a5cd39]/90 active:scale-95"
                  }`}
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
            <div className="flex items-center justify-between mt-2">
              <div className="text-xs text-gray-500">
                Press Enter to send, Shift+Enter for new line
              </div>
              {messages.length > 0 && (
                <button
                  onClick={() => setShowExamples(true)}
                  className="text-xs text-[#a5cd39] hover:text-[#a5cd39]/80 font-medium flex items-center"
                >
                  <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Show Examples
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Examples Panel (shown when toggled) */}
        {showExamples && messages.length > 0 && (
          <div className="mt-6 bg-gray-50 rounded-2xl p-6 border border-gray-200">
            <h3 className="text-lg font-semibold text-gray-700 mb-4">Quick Examples:</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {examplePrompts.map((prompt) => (
                <button
                  key={prompt.id}
                  onClick={() => handleExampleClick(prompt.text)}
                  className={`group rounded-xl p-4 text-left transition-all duration-200 hover:scale-102 bg-gradient-to-r ${prompt.gradient} hover:shadow-md border border-white/30`}
                >
                  <div className="flex items-center mb-2">
                    <span className="text-lg mr-2">{prompt.icon}</span>
                    <span className="text-white text-sm font-medium">
                      {prompt.text.split(' ').slice(0, 4).join(' ')}...
                    </span>
                  </div>
                  <p className="text-white/80 text-xs">
                    {prompt.description}
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}