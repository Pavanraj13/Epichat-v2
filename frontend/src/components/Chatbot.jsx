import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, X, Loader, Mic, MicOff, Volume2 } from 'lucide-react';
import { API_BASE } from '../lib/api';

// ─────────────────────────────────────────────────────────────────────────────
// Animated typing dots indicator
// ─────────────────────────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="chat-message-row ai">
      <div className="chat-bubble ai-bubble" style={{ padding: '10px 14px' }}>
        <span style={{ display: 'inline-flex', gap: 5, alignItems: 'center' }}>
          {[0, 1, 2].map(i => (
            <span
              key={i}
              style={{
                width: 7, height: 7, borderRadius: '50%',
                background: 'var(--accent)',
                display: 'inline-block',
                animation: `typingBounce 1.2s ${i * 0.2}s ease-in-out infinite`,
              }}
            />
          ))}
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Chatbot component
// ─────────────────────────────────────────────────────────────────────────────
export default function Chatbot({ onClose }) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      text: "Hello! I'm EpiChat AI — your epilepsy & EEG assistant. Ask me anything about seizure results, precautions, medications, or first aid. How can I help you today?",
    },
  ]);
  const [inputVal,  setInputVal]  = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const [voiceSupported, setVoiceSupported] = useState(false);
  
  const endRef   = useRef(null);
  const inputRef = useRef(null);
  const recognitionRef = useRef(null);

  // Auto-scroll on new messages
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // ── Speech Recognition Setup ───────────────────────────────────────────────
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      // Firefox, Safari, or unsupported browser
      setVoiceSupported(false);
      return;
    }

    setVoiceSupported(true);
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setInputVal(transcript);
      setIsListening(false);
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      if (event.error === 'not-allowed') {
        setVoiceError('Mic blocked — allow microphone in browser settings');
      } else if (event.error === 'no-speech') {
        setVoiceError('No speech detected — try again');
      } else if (event.error === 'network') {
        setVoiceError('Network error — voice needs internet connection');
      } else {
        setVoiceError(`Voice error: ${event.error}`);
      }
      setIsListening(false);
      setTimeout(() => setVoiceError(''), 4000);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
  }, []);

  const toggleListening = () => {
    if (!voiceSupported) {
      setVoiceError('Voice not supported — use Chrome or Edge browser');
      setTimeout(() => setVoiceError(''), 4000);
      return;
    }
    if (isListening) {
      recognitionRef.current?.stop();
    } else {
      setVoiceError('');
      try {
        recognitionRef.current?.start();
        setIsListening(true);
      } catch (err) {
        console.error('Failed to start recognition:', err);
        setVoiceError('Could not start mic — allow microphone access in browser');
        setTimeout(() => setVoiceError(''), 4000);
      }
    }
  };

  // ── Text-to-Speech ─────────────────────────────────────────────────────────
  const speakText = (text) => {
    if ('speechSynthesis' in window) {
      // Cancel any ongoing speech
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  };

  // ── Send message to backend proxy ──────────────────────────────────────────
  const sendToBackend = async (text, history) => {
    // Build conversation in the format the backend expects: { message, history }
    const payload = {
      message: text,
      history: history.map(m => ({
        role:    m.role === 'assistant' ? 'assistant' : 'user',
        text:    m.text,
      })),
    };

    const res = await fetch(`${API_BASE}/api/chat`, {
      method:  'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('epichat_token') || ''}`
      },
      body:    JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const data = await res.json();
    return data.reply;
  };

  // ── Handle submit ──────────────────────────────────────────────────────────
  const handleSend = async (e) => {
    if (e) e.preventDefault();
    const text = inputVal.trim();
    if (!text || isLoading) return;

    // Add user message immediately
    const userMsg = { id: Date.now(), role: 'user', text };
    const historyBeforeResponse = [...messages];
    setMessages(prev => [...prev, userMsg]);
    setInputVal('');
    setIsLoading(true);
    inputRef.current?.focus();

    try {
      const reply = await sendToBackend(text, historyBeforeResponse);
      const aiMsg = { id: Date.now() + 1, role: 'assistant', text: reply };
      setMessages(prev => [...prev, aiMsg]);
      // Optional: Auto-speak response if you want, but better as a button
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          text: '🤖 AI assistant temporarily unavailable. Please try again in a moment.',
        },
      ]);
      console.warn('[EpiChat] Chat backend error:', err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // ── Keyboard shortcut: Enter to send, Shift+Enter for newline ─────────────
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  return (
    <div className="glass-panel chatbot-container">

      {/* ── HEADER ──────────────────────────────────────────────────────── */}
      <div className="chatbot-header">
        <div style={{
          width: 34, height: 34, borderRadius: '50%',
          background: 'linear-gradient(135deg,#6366f1,#c084fc)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, marginRight: 10,
        }}>
          <Bot size={17} color="white" />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>EpiChat AI Assistant</h3>
          <div style={{ fontSize: '0.72rem', color: isLoading ? '#f59e0b' : 'var(--success)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: isLoading ? '#f59e0b' : 'var(--success)', display: 'inline-block', animation: isLoading ? 'pulse 1s ease infinite' : 'none' }} />
            {isLoading ? 'Thinking…' : 'Online'}
            {isListening && <span style={{ color: '#ef4444', marginLeft: 8 }}>• Listening...</span>}
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            id="chatbot-close-btn"
            aria-label="Close chat"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: 4, borderRadius: 8, display: 'flex', alignItems: 'center', transition: 'color 0.2s' }}
            onMouseEnter={e => { e.currentTarget.style.color = 'white'; }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-secondary)'; }}
          >
            <X size={18} />
          </button>
        )}
      </div>

      {/* ── MESSAGES ─────────────────────────────────────────────────────── */}
      <div className="chatbot-messages">
        {messages.map(msg => (
          <div key={msg.id} className={`chat-message-row ${msg.role === 'assistant' ? 'ai' : 'user'}`}>
            <div
              className={`chat-bubble ${msg.role === 'assistant' ? 'ai-bubble' : 'user-bubble'}`}
              style={{ whiteSpace: 'pre-wrap', lineHeight: 1.55, position: 'relative' }}
            >
              {msg.text}
              {msg.role === 'assistant' && msg.id !== 1 && (
                <button 
                  onClick={() => speakText(msg.text)}
                  title="Speak Response"
                  style={{ 
                    position: 'absolute', bottom: -20, right: 0, 
                    background: 'none', border: 'none', color: 'var(--text-secondary)',
                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
                    fontSize: '0.7rem'
                  }}
                >
                  <Volume2 size={12} /> Speak
                </button>
              )}
            </div>
          </div>
        ))}

        {/* Typing indicator — replaces placeholder while awaiting API */}
        {isLoading && <TypingIndicator />}

        <div ref={endRef} />
      </div>

      {/* ── ERROR DISPLAY ─────────────────────────────────────────────────── */}
      {voiceError && (
        <div style={{ color: '#ef4444', fontSize: '0.75rem', textAlign: 'center', padding: '4px 0' }}>
          {voiceError}
        </div>
      )}

      {/* ── INPUT ─────────────────────────────────────────────────────────── */}
      <form onSubmit={handleSend} className="chatbot-input-container">
        <button
          type="button"
          onClick={toggleListening}
          className={`chat-voice-btn ${isListening ? 'listening' : ''}`}
          title={!voiceSupported ? 'Voice input requires Chrome or Edge browser' : (isListening ? 'Click to stop listening' : 'Click to speak')}
          style={{ 
            background: 'none', border: 'none', 
            color: !voiceSupported ? 'var(--text-secondary)' : (isListening ? '#ef4444' : 'var(--text-secondary)'),
            opacity: !voiceSupported ? 0.4 : 1,
            cursor: !voiceSupported ? 'not-allowed' : 'pointer', 
            marginRight: 8, display: 'flex', alignItems: 'center'
          }}
        >
          {isListening ? <MicOff size={18} /> : <Mic size={18} />}
        </button>
        <input
          ref={inputRef}
          id="chatbot-input"
          type="text"
          value={inputVal}
          onChange={e => setInputVal(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isLoading ? 'Waiting for response…' : (isListening ? 'Listening...' : 'Ask about EEG results, seizures…')}
          className="chat-input"
          disabled={isLoading}
          autoComplete="off"
        />
        <button
          type="submit"
          id="chatbot-send-btn"
          className="chat-send-btn"
          disabled={isLoading || !inputVal.trim()}
          aria-label="Send message"
        >
          {isLoading
            ? <Loader size={16} style={{ animation: 'chatSpin 0.8s linear infinite' }} />
            : <Send size={16} />
          }
        </button>
      </form>

      <style>{`
        @keyframes typingBounce {
          0%, 60%, 100% { transform: translateY(0);   opacity: 0.4; }
          30%            { transform: translateY(-6px); opacity: 1;   }
        }
        @keyframes chatSpin { to { transform: rotate(360deg); } }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.3; }
        }
        .chat-voice-btn.listening {
          animation: pulse 1s ease infinite;
        }
      `}</style>
    </div>
  );
}

