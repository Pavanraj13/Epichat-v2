import React, { useState, useRef } from 'react';
import Chatbot from './Chatbot';
import { UploadCloud, CheckCircle, AlertTriangle, LogOut, MessageSquare, X, Activity } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { API_BASE } from '../lib/api';

export default function Dashboard() {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  
  // 'idle' | 'analyzing' | 'result'
  const [status, setStatus] = useState('idle');
  const [resultVal, setResultVal] = useState(null); // 'healthy' | 'epileptic' | 'seizure'
  const [isChatOpen, setIsChatOpen] = useState(false);
  
  const inputRef = useRef(null);
  const navigate = useNavigate();

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (uploadedFile) => {
    const ext = uploadedFile.name.split('.').pop().toLowerCase();
    if (ext === 'edf' || ext === 'txt') {
      setFile(uploadedFile);
      setStatus('idle');
      setResultVal(null);
    } else {
      setFile(null);
      alert('Invalid Sequence Type! Please upload a .edf or .txt file.');
    }
  };

  // We rotate through the 3 states so you can predictably see all of them during demo
  const submitFile = async () => {
    if (!file) return;
    setStatus('analyzing');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Network response was not ok');
      }
      
      const data = await response.json();

      // UI Wait for analyzing anim for 2 seconds to make it look cool, then show real result
      setTimeout(() => {
        setResultVal(data.result);
        setStatus('result');
      }, 2000); 
    } catch (error) {
      console.error('Error uploading file:', error);
      alert('Upload failed. Please check your connection and try again.');
      setStatus('idle');
    }
  };

  return (
    <div className="app-canvas flex-col">
      {/* Decorative Orbs */}
      <div className="orb orb-pink" style={{ top: '-10%', left: '-10%' }}></div>
      <div className="orb orb-blue" style={{ bottom: '-10%', right: '-5%' }}></div>
      <div className="orb orb-accent" style={{ top: '40%', left: '50%', transform: 'translate(-50%, -50%)', opacity: 0.2 }}></div>

      <nav className="dashboard-nav glass-panel">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Activity size={24} className="neon-icon" />
          <h1 className="title neon-text" style={{ fontSize: '1.5rem', margin: 0 }}>EpiChat</h1>
        </div>
        <button className="btn-secondary nav-btn" onClick={() => navigate('/login')}>
          <LogOut size={16} style={{marginRight: '8px'}} /> Disconnect
        </button>
      </nav>

      <main className="dashboard-main flex-center">
        {(status === 'idle') && (
          <div className="upload-station slide-up">
            <div 
               className={`glass-panel hologram-box ${dragActive ? 'dropzone-active' : ''}`}
               onDragEnter={handleDrag}
               onDragLeave={handleDrag}
               onDragOver={handleDrag}
               onDrop={handleDrop}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".edf,.txt"
                onChange={handleChange}
                style={{ display: 'none' }}
              />
              
              <div className="hologram-content">
                <UploadCloud size={64} className="icon-glow" />
                <h2 className="title" style={{ fontSize: '1.8rem', marginTop: '1rem' }}>Initiate Data Link</h2>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>Drop your .edf telemetry or .txt signature here</p>
                
                <button 
                   className="btn-primary interactive-element" 
                   onClick={(e) => { e.stopPropagation(); inputRef.current.click(); }}
                >
                   Browse System
                </button>
              </div>
            </div>

            {file && (
              <div className="glass-panel file-ready-plate pop-in">
                <div className="file-info text-left">
                  <h3 style={{ margin: 0, color: 'var(--success)', textTransform: 'uppercase', letterSpacing: '1px', fontSize: '0.9rem' }}>Target Locked</h3>
                  <p className="neon-text" style={{ margin: 0, fontSize: '1.2rem' }}>{file.name}</p>
                </div>
                <button className="btn-primary run-btn interactive-element" onClick={submitFile}>
                  Execute Neural Scan
                </button>
              </div>
            )}
          </div>
        )}

        {status === 'analyzing' && (
          <div className="glass-panel analyzing-card slide-up">
            <h2 className="title neon-text pulse-fast">Processing Telemetry</h2>
            <div className="brainwave-loader">
              <svg viewBox="0 0 100 20" preserveAspectRatio="none">
                <polyline className="wave-line" points="0 10, 20 10, 25 2, 35 18, 45 4, 50 16, 55 10, 80 10, 85 8, 90 12, 100 10" />
                <polyline className="wave-line-glow" points="0 10, 20 10, 25 2, 35 18, 45 4, 50 16, 55 10, 80 10, 85 8, 90 12, 100 10" />
              </svg>
            </div>
            <p className="status-text gradient-animate">Extracting BIOT Features...</p>
          </div>
        )}

        {status === 'result' && (
          <div className="glass-panel result-card slide-up">
            
            {resultVal === 'healthy' && (
              <div className="result-content safe-state">
                <div className="result-icon-ring safe-ring">
                   <CheckCircle size={56} className="icon-safe" />
                </div>
                <h2 className="title text-safe">Healthy</h2>
                <p>The analyzed timeframe shows standard brainwave activity. No abnormal or epileptic signatures were detected.</p>
              </div>
            )}

            {resultVal === 'epileptic' && (
              <div className="result-content alert-state">
                <div className="result-icon-ring" style={{ background: 'rgba(245, 158, 11, 0.1)', border: '2px solid #f59e0b', boxShadow: '0 0 30px rgba(245, 158, 11, 0.2)'}}>
                   <Activity size={56} style={{ color: '#f59e0b'}} />
                </div>
                <h2 className="title" style={{ color: '#f59e0b', textShadow: '0 0 10px rgba(245, 158, 11, 0.4)' }}>Epileptic</h2>
                <p>Interictal epileptic discharges were identified in the background activity, indicating underlying epilepsy, but no active seizure occurred in this timeframe.</p>
              </div>
            )}

            {resultVal === 'seizure' && (
              <div className="result-content alert-state">
                <div className="result-icon-ring alert-ring">
                   <AlertTriangle size={56} className="icon-alert" />
                </div>
                <h2 className="title text-alert">Seizure Detected</h2>
                <p>Critical abnormal waveforms consistent with active epileptic seizure activity have been definitively identified.</p>
              </div>
            )}

            <button className="btn-secondary mt-2 interactive-element" onClick={() => setStatus('idle')} style={{ marginTop: '2rem' }}>
              Scan Another Sequence
            </button>
          </div>
        )}
      </main>

      {/* Floating Chatbot Toggle button */}
      <button 
        className={`fab-chat ${isChatOpen ? 'active' : ''}`} 
        onClick={() => setIsChatOpen(!isChatOpen)}
      >
        {isChatOpen ? <X size={24} /> : <MessageSquare size={24} />}
      </button>

      {/* Floating Window Container for Chatbot */}
      <div className={`floating-chat-window ${isChatOpen ? 'visible' : ''}`}>
         <Chatbot />
      </div>

    </div>
  );
}
