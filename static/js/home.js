// Hamburger menu functionality for mobile
document.querySelector('.hamburger').addEventListener('click', function() {
    const navItems = document.querySelector('.nav-items');
    navItems.style.display = navItems.style.display === 'flex' ? 'none' : 'flex';
});

// Adjust navigation for mobile on resize
window.addEventListener('resize', function() {
    const navItems = document.querySelector('.nav-items');
    if (window.innerWidth > 768) {
        navItems.style.display = 'flex';
    } else {
        navItems.style.display = 'none';
    }
});

// Initialize for mobile view
if (window.innerWidth <= 768) {
    document.querySelector('.nav-items').style.display = 'none';
}
// Add this to your existing script section, after your current code:

// Enhanced Chatbot Functionality
document.addEventListener('DOMContentLoaded', function() {
    const chatbotBtn = document.getElementById("chatbot-btn");
    const chatWindow = document.getElementById("chat-window");
    const closeChatBtn = document.getElementById("close-chat");
    const chatMessages = document.getElementById("chat-messages");
    const chatInput = document.getElementById("chat-input");
    const chatSend = document.getElementById("chat-send");
    const quickReplies = document.querySelectorAll('.quick-reply-btn');
    const notificationBadge = document.getElementById("notification-badge");
    const speechToggleBtn = document.getElementById("speech-toggle");
    const voiceInputBtn = document.getElementById("voice-input");

    let isOpen = false;
    let speechEnabled = true;
    let currentSpeech = null;
    let recognition = null;
    let isListening = false;
    
    // Language detection for speech
    function detectTextLanguage(text) {
        const hindiChars = /[\u0900-\u097F]/g;
        const marathiChars = /[\u0900-\u097F]/g;
        
        const hindiWords = ['कैसे', 'क्या', 'हाँ', 'नहीं', 'धन्यवाद', 'कहाँ', 'मुझे', 'आप', 'हम', 'वह', 'मैं', 'है', 'का', 'की', 'में', 'से', 'और', 'भी'];
        const marathiWords = ['कसे', 'काय', 'होय', 'नाही', 'धन्यवाद', 'कुठे', 'मला', 'तुम्ही', 'आम्ही', 'तो', 'आहे', 'चा', 'ची', 'मध्ये', 'आणि', 'सुद्धा'];
        
        const hindiCount = hindiWords.filter(word => text.includes(word)).length;
        const marathiCount = marathiWords.filter(word => text.includes(word)).length;
        const devanagariCount = (text.match(hindiChars) || []).length;
        
        if (devanagariCount > 5) {
            return hindiCount > marathiCount ? 'hindi' : 'marathi';
        }
        return 'english';
    }

    // Text-to-Speech Functions
    function initializeSpeech() {
        if ('speechSynthesis' in window) {
            console.log('Speech synthesis available');
            
            // Wake up speech synthesis (some browsers need this)
            const testUtterance = new SpeechSynthesisUtterance('');
            speechSynthesis.speak(testUtterance);
            speechSynthesis.cancel();
            
            updateSpeechButton();
            console.log('Speech synthesis initialized');
        } else {
            speechToggleBtn.style.display = 'none';
            console.log('Text-to-Speech not supported in this browser');
        }
    }

    function updateSpeechButton() {
        const icon = speechToggleBtn.querySelector('i');
        if (speechEnabled) {
            icon.className = 'fas fa-volume-up';
            speechToggleBtn.title = 'Mute Speech';
            speechToggleBtn.classList.remove('muted');
        } else {
            icon.className = 'fas fa-volume-mute';
            speechToggleBtn.title = 'Enable Speech';
            speechToggleBtn.classList.add('muted');
        }
    }

    function stopCurrentSpeech() {
        console.log('🛑 Stopping all speech (including queue)');
        
        // Stop current speech
        if (currentSpeech) {
            currentSpeech.onend = null; // Remove event handlers to prevent issues
            currentSpeech.onerror = null;
            speechSynthesis.cancel();
            currentSpeech = null;
        }
        
        // Clear speech queue
        if (typeof speechQueue !== 'undefined') {
            speechQueue = [];
        }
        if (typeof isSpeakingQueue !== 'undefined') {
            isSpeakingQueue = false;
        }
        
        // Update UI
        speechToggleBtn.classList.remove('speaking');
        
        // Force stop all speech synthesis - sometimes cancel() isn't enough
        if ('speechSynthesis' in window) {
            speechSynthesis.cancel();
            // Small delay to ensure cancellation takes effect
            setTimeout(() => {
                if (speechSynthesis.speaking || speechSynthesis.pending) {
                    speechSynthesis.cancel();
                    console.log('🔧 Force stopped persistent speech');
                }
            }, 50);
        }
        
        // Clear any pending speech timeouts
        if (window.speechTimeout) {
            clearTimeout(window.speechTimeout);
            window.speechTimeout = null;
        }
        
        console.log('✅ All speech stopped and queue cleared');
    }
    
    function stopAllSpeechAndRecognition() {
        // Stop text-to-speech more aggressively
        stopCurrentSpeech();
        
        // Additional force stop for any remaining speech
        if ('speechSynthesis' in window) {
            speechSynthesis.cancel();
            // Multiple attempts to ensure speech stops
            let attempts = 0;
            const forceStop = () => {
                if ((speechSynthesis.speaking || speechSynthesis.pending) && attempts < 3) {
                    speechSynthesis.cancel();
                    attempts++;
                    setTimeout(forceStop, 100);
                }
            };
            forceStop();
        }
        
        // Stop speech recognition
        if (recognition && isListening) {
            recognition.stop();
            isListening = false;
            voiceInputBtn.classList.remove('listening', 'processing');
            voiceInputBtn.title = 'Click to speak your question';
            voiceInputBtn.querySelector('i').className = 'fas fa-microphone';
        }
        
        // Clear any pending speech timeouts
        if (window.speechTimeout) {
            clearTimeout(window.speechTimeout);
            window.speechTimeout = null;
        }
    }

    // Global speech queue for handling long text
    let speechQueue = [];
    let isSpeakingQueue = false;

    // 🔧 DEBUG: Test speech chunking system
    window.testLongSpeech = function() {
        const longText = "This is a test of the new speech chunking system. It should break long text into smaller pieces and speak each piece clearly without cutting off. The old system would stop after just a few words, but this new system should speak the complete text by breaking it into manageable chunks. Each chunk will be spoken separately with a small pause between them. This ensures that even very long responses are read completely.";
        console.log('🧪 Testing long speech with chunking system...');
        speakText(longText);
    };

    function speakText(text) {
        console.log('🔊 speakText called with:', text.substring(0, 50) + '...');
        
        if (!speechEnabled) {
            console.log('❌ Speech disabled');
            return;
        }
        
        if (!('speechSynthesis' in window)) {
            console.log('❌ Speech synthesis not supported');
            return;
        }

        // Stop current speech and clear queue
        if (currentSpeech && speechSynthesis.speaking) {
            console.log('🛑 Stopping current speech');
            speechSynthesis.cancel();
            currentSpeech = null;
        }
        speechQueue = [];
        isSpeakingQueue = false;

        // Enhanced text cleaning for better speech synthesis
        const cleanText = text
            // Remove ALL emojis and special characters
            .replace(/[🎯🚀💼🌟📚👋🤖⚡💡🎓🏆✨📊🔥💪🎉🌈💼📈🎪🎭🎨🎵🎸🎹🥇🏅🎖️💫🍽️⏰🌅🌙📝🔧✅❌⚠️🏛️🇮🇳📧🎂💰🔍💵🎁📅🗓️📋]/g, '')
            // Remove HTML tags completely
            .replace(/<br>/g, '. ')
            .replace(/<\/?[^>]+(>|$)/g, '')
            // Clean markdown formatting
            .replace(/\*\*(.*?)\*\*/g, '$1')
            .replace(/\*(.*?)\*/g, '$1')
            .replace(/\#+ /g, '')
            .replace(/\• /g, '')
            .replace(/\n+/g, '. ')
            .replace(/\\n/g, '. ')
            // Fix spacing and special terms
            .replace(/\s+/g, ' ')
            .replace(/PM Internship/g, 'Prime Minister Internship')
            .replace(/₹/g, 'rupees ')
            .replace(/8L/g, '8 lakhs')
            .replace(/\bL\b/g, 'lakhs')
            .replace(/\bK\b/g, 'thousand')
            // Remove leftover symbols
            .replace(/[•▪▫◦‣⁃]/g, '')
            .replace(/[\[\]{}]/g, '')
            .trim();

        if (cleanText.length === 0) {
            console.log('❌ No text to speak after cleaning');
            return;
        }
        
        console.log('✅ Clean text to speak (length:', cleanText.length + '):', cleanText.substring(0, 100) + '...');

        // 🚀 NEW: Split long text into chunks for better speech synthesis
        const chunks = splitTextIntoChunks(cleanText, 200); // 200 characters per chunk
        console.log('📝 Split into', chunks.length, 'chunks for better speech');
        
        if (chunks.length === 1) {
            // Short text - speak directly
            speakSingleText(cleanText);
        } else {
            // Long text - use queue system
            speechQueue = chunks;
            speakNextInQueue();
        }
    }

    // Helper function to split text into manageable chunks
    function splitTextIntoChunks(text, maxLength = 200) {
        if (text.length <= maxLength) {
            return [text];
        }

        const chunks = [];
        const sentences = text.split('. ');
        let currentChunk = '';

        for (let sentence of sentences) {
            const proposedChunk = currentChunk + (currentChunk ? '. ' : '') + sentence;
            
            if (proposedChunk.length <= maxLength) {
                currentChunk = proposedChunk;
            } else {
                if (currentChunk) {
                    chunks.push(currentChunk);
                    currentChunk = sentence;
                } else {
                    // Single sentence is too long, split by words
                    const words = sentence.split(' ');
                    let wordChunk = '';
                    for (let word of words) {
                        const proposedWordChunk = wordChunk + (wordChunk ? ' ' : '') + word;
                        if (proposedWordChunk.length <= maxLength) {
                            wordChunk = proposedWordChunk;
                        } else {
                            if (wordChunk) chunks.push(wordChunk);
                            wordChunk = word;
                        }
                    }
                    if (wordChunk) chunks.push(wordChunk);
                    currentChunk = '';
                }
            }
        }

        if (currentChunk) {
            chunks.push(currentChunk);
        }

        return chunks.filter(chunk => chunk.trim().length > 0);
    }

    // Queue management for long speech
    function speakNextInQueue() {
        if (speechQueue.length === 0 || !speechEnabled) {
            isSpeakingQueue = false;
            speechToggleBtn.classList.remove('speaking');
            console.log('✅ Speech queue completed');
            return;
        }

        if (isSpeakingQueue) {
            console.log('⏳ Already speaking queue, waiting...');
            return;
        }

        isSpeakingQueue = true;
        const textChunk = speechQueue.shift();
        console.log('🗣️ Speaking chunk:', textChunk.substring(0, 50) + '...');
        
        speakSingleText(textChunk, () => {
            // On completion, speak next chunk
            setTimeout(() => {
                isSpeakingQueue = false;
                speakNextInQueue();
            }, 300); // Small pause between chunks
        });
    }

    // Speak a single text chunk
    function speakSingleText(text, onComplete = null) {
        try {
            currentSpeech = new SpeechSynthesisUtterance(text);
            
            // Detect language and configure speech settings
            const detectedLang = detectTextLanguage(text);
            
            // Configure speech settings for MAXIMUM AUDIBILITY
            if (detectedLang === 'hindi') {
                currentSpeech.rate = 0.7;   // Slower for clarity
                currentSpeech.pitch = 1.1;  // Slightly higher pitch for better hearing
                currentSpeech.volume = 1.0; // Maximum volume
            } else if (detectedLang === 'marathi') {
                currentSpeech.rate = 0.7;   // Slower for clarity
                currentSpeech.pitch = 1.1;  // Slightly higher pitch for better hearing
                currentSpeech.volume = 1.0; // Maximum volume
            } else {
                currentSpeech.rate = 0.75;  // Optimal speed for clarity
                currentSpeech.pitch = 1.1;  // Higher pitch for better audibility
                currentSpeech.volume = 1.0; // Maximum volume
            }
            
            console.log('Speech settings:', {
                rate: currentSpeech.rate,
                pitch: currentSpeech.pitch,
                volume: currentSpeech.volume,
                lang: detectedLang
            });

            // Enhanced voice selection for MAXIMUM VOLUME and CLARITY
            const voices = speechSynthesis.getVoices();
            let preferredVoice = null;
            
            console.log('Available voices for selection:', voices.length);
            
            if (detectedLang === 'hindi') {
                // Priority order for Hindi: Clear > Indian English > Any English
                preferredVoice = voices.find(voice => 
                    voice.lang.includes('hi') && !voice.name.toLowerCase().includes('whisper')
                ) || voices.find(voice => 
                    voice.lang.startsWith('en-IN') && !voice.name.toLowerCase().includes('whisper')
                ) || voices.find(voice => 
                    voice.lang.startsWith('en-US') && 
                    (voice.name.includes('David') || voice.name.includes('Mark') || voice.name.includes('Google'))
                );
            } else if (detectedLang === 'marathi') {
                // Priority for Marathi: Regional > Indian English > Clear English
                preferredVoice = voices.find(voice => 
                    voice.lang.includes('mr') && !voice.name.toLowerCase().includes('whisper')
                ) || voices.find(voice => 
                    voice.lang.startsWith('en-IN') && !voice.name.toLowerCase().includes('whisper')
                ) || voices.find(voice => 
                    voice.lang.startsWith('en-US') && 
                    (voice.name.includes('David') || voice.name.includes('Mark') || voice.name.includes('Google'))
                );
            } else {
                // Priority for English: Loud system voices > Natural voices > Any English
                preferredVoice = voices.find(voice => 
                    voice.lang.startsWith('en') && 
                    (voice.name.includes('David') || voice.name.includes('Mark') || 
                     voice.name.includes('Microsoft') || voice.name.includes('Google')) &&
                    !voice.name.toLowerCase().includes('whisper')
                ) || voices.find(voice => 
                    voice.lang.startsWith('en-US') && 
                    (voice.name.includes('Natural') || voice.name.includes('Enhanced')) &&
                    !voice.name.toLowerCase().includes('whisper')
                ) || voices.find(voice => 
                    voice.lang.startsWith('en') && !voice.name.toLowerCase().includes('whisper')
                );
            }
            
            if (preferredVoice) {
                currentSpeech.voice = preferredVoice;
                console.log('Selected voice for maximum volume:', preferredVoice.name, '(' + preferredVoice.lang + ')');
            } else {
                console.log('Using default voice - may be quieter');
            }

            // Enhanced event handlers for queue system
            currentSpeech.onstart = () => {
                console.log('🎤 Speech chunk started');
                speechToggleBtn.classList.add('speaking');
                
                // Set a timeout for this chunk (max 15 seconds per chunk)
                window.speechTimeout = setTimeout(() => {
                    if (currentSpeech && speechSynthesis.speaking) {
                        console.log('⏰ Speech chunk timeout - moving to next');
                        speechSynthesis.cancel();
                        if (onComplete) onComplete();
                    }
                }, 15000);
            };

            currentSpeech.onend = () => {
                console.log('✅ Speech chunk completed successfully');
                currentSpeech = null;
                if (window.speechTimeout) {
                    clearTimeout(window.speechTimeout);
                    window.speechTimeout = null;
                }
                
                // Call completion callback for queue management
                if (onComplete) {
                    onComplete();
                } else {
                    // Single speech completion
                    speechToggleBtn.classList.remove('speaking');
                }
            };

            currentSpeech.onerror = (event) => {
                console.log('❌ Speech chunk error:', event.error);
                currentSpeech = null;
                if (window.speechTimeout) {
                    clearTimeout(window.speechTimeout);
                    window.speechTimeout = null;
                }
                
                // Continue with next chunk even if this one failed
                if (onComplete) {
                    console.log('🔄 Continuing to next chunk despite error');
                    onComplete();
                } else {
                    speechToggleBtn.classList.remove('speaking');
                }
            };

            const availableVoices = speechSynthesis.getVoices();
            console.log('About to speak text, voices available:', availableVoices.length);
            console.log('Speech synthesis ready:', !speechSynthesis.speaking && !speechSynthesis.pending);
            
            // Audio system checks
            console.log('🔊 AUDIO DEBUG INFO:');
            console.log('- Browser audio context state:', window.AudioContext ? 'Available' : 'Not supported');
            console.log('- Speech synthesis paused:', speechSynthesis.paused);
            console.log('- Current speech volume:', currentSpeech.volume);
            console.log('- Available voices:', availableVoices.map(v => v.name).slice(0, 3));
            
            // If no voices are loaded yet, wait for them
            if (availableVoices.length === 0) {
                console.log('❌ No voices loaded yet, waiting...');
                speechSynthesis.onvoiceschanged = () => {
                    console.log('✅ Voices loaded, trying speech again');
                    const newVoices = speechSynthesis.getVoices();
                    console.log('New voices available:', newVoices.length);
                    speechSynthesis.speak(currentSpeech);
                };
                return;
            }
            
            // Resume speech synthesis if paused (common browser issue)
            if (speechSynthesis.paused) {
                console.log('Speech was paused, resuming...');
                speechSynthesis.resume();
            }
            
            // Speak the text chunk
            speechSynthesis.speak(currentSpeech);
            console.log('✅ Speech chunk sent - length:', text.length, 'chars');
        } catch (error) {
            console.log('❌ Speech synthesis error:', error);
            currentSpeech = null;
            if (onComplete) {
                onComplete();
            } else {
                speechToggleBtn.classList.remove('speaking');
            }
        }
    }

    // Speech toggle button event - Simplified to only enable/mute
    speechToggleBtn.addEventListener('click', () => {
        // Always stop current speech first
        if (currentSpeech && speechSynthesis.speaking) {
            stopCurrentSpeech();
        }
        
        // Toggle speech enabled/disabled
        speechEnabled = !speechEnabled;
        updateSpeechButton();
        
        // Test speech synthesis when enabling (browser activation) - LOUD VERSION
        if (speechEnabled && 'speechSynthesis' in window) {
            console.log('🔊 Testing speech synthesis activation with MAXIMUM VOLUME...');
            try {
                const testSpeech = new SpeechSynthesisUtterance('Speech enabled at maximum volume');
                testSpeech.volume = 1.0; // Maximum volume
                testSpeech.rate = 0.7;   // Slower for clarity
                testSpeech.pitch = 1.1;  // Higher pitch for audibility
                
                // Use loudest available voice
                const voices = speechSynthesis.getVoices();
                if (voices.length > 0) {
                    const loudVoice = voices.find(voice => 
                        voice.lang.startsWith('en') && 
                        (voice.name.includes('David') || voice.name.includes('Mark') || voice.name.includes('Microsoft')) &&
                        !voice.name.toLowerCase().includes('whisper')
                    ) || voices.find(voice => voice.lang.startsWith('en'));
                    
                    if (loudVoice) {
                        testSpeech.voice = loudVoice;
                        console.log('Using loud voice for activation test:', loudVoice.name);
                    }
                }
                
                testSpeech.onstart = () => {
                    console.log('✅ LOUD speech activation test started - you should hear this CLEARLY!');
                };
                testSpeech.onend = () => {
                    console.log('Speech activation test completed - if you heard that, volume is working!');
                };
                testSpeech.onerror = (e) => {
                    console.log('❌ Speech activation test failed:', e);
                    console.log('Try: testSpeech() in console for detailed audio debug');
                };
                speechSynthesis.speak(testSpeech);
            } catch (error) {
                console.log('❌ Speech activation error:', error);
            }
        }
        
        // Show simple feedback
        const feedbackText = speechEnabled ? 
            '🔊 Speech Enabled' : 
            '🔇 Speech Muted';
        addMessage(feedbackText, false, { personalized: false, responseTime: '0.1' });
    });

    // Initialize speech when page loads
    initializeSpeech();

    // Ensure voices are loaded (some browsers load them asynchronously)
    if ('speechSynthesis' in window) {
        speechSynthesis.onvoiceschanged = () => {
            initializeSpeech();
        };
    }

    // Global test function for debugging audio issues
    window.testSpeech = function(testText = "Hello, this is an audio test. Can you hear me?") {
        console.log('🔊 RUNNING AUDIO TEST...');
        
        // Check system audio
        console.log('System checks:');
        console.log('- Speech synthesis supported:', 'speechSynthesis' in window);
        console.log('- Voices available:', speechSynthesis.getVoices().length);
        console.log('- Currently speaking:', speechSynthesis.speaking);
        console.log('- Currently paused:', speechSynthesis.paused);
        
        if (!('speechSynthesis' in window)) {
            console.log('❌ Speech synthesis not supported in this browser');
            return;
        }
        
        // Cancel any existing speech
        speechSynthesis.cancel();
        
        // Create test utterance with MAXIMUM VOLUME settings
        const testUtterance = new SpeechSynthesisUtterance(testText);
        testUtterance.volume = 1.0; // Maximum volume
        testUtterance.rate = 0.7;   // Slower for better clarity and projection
        testUtterance.pitch = 1.1;  // Higher pitch for better audibility
        
        // Get the LOUDEST available voice
        const voices = speechSynthesis.getVoices();
        if (voices.length > 0) {
            // Priority: System voices (usually louder) > Natural voices > Any voice
            const loudVoice = voices.find(voice => 
                voice.lang.startsWith('en') && 
                (voice.name.includes('David') || voice.name.includes('Mark') || 
                 voice.name.includes('Microsoft') || voice.name.includes('Google')) &&
                !voice.name.toLowerCase().includes('whisper') &&
                !voice.name.toLowerCase().includes('novelty')
            ) || voices.find(voice => 
                voice.lang.startsWith('en') && 
                !voice.name.toLowerCase().includes('whisper') &&
                !voice.name.toLowerCase().includes('novelty')
            ) || voices[0];
            
            testUtterance.voice = loudVoice;
            console.log('🔊 Using LOUD voice for test:', loudVoice.name, '(' + loudVoice.lang + ')');
        }
        
        // Event handlers for debugging
        testUtterance.onstart = () => {
            console.log('✅ AUDIO TEST STARTED - You should hear sound now!');
            console.log('📢 If you hear nothing, check:');
            console.log('   1. System volume');
            console.log('   2. Browser audio permissions');
            console.log('   3. Headphones/speakers connection');
        };
        
        testUtterance.onend = () => {
            console.log('✅ AUDIO TEST COMPLETED');
        };
        
        testUtterance.onerror = (event) => {
            console.log('❌ AUDIO TEST ERROR:', event.error);
            console.log('Common fixes:');
            console.log('   - Try clicking somewhere on the page first');
            console.log('   - Check browser permissions');
            console.log('   - Try a different browser');
        };
        
        // Speak the test
        speechSynthesis.speak(testUtterance);
        console.log('🎵 Audio test initiated...');
    };

    // Global function to find and test the loudest voice
    window.findLoudestVoice = function() {
        console.log('🔊 FINDING LOUDEST VOICE...');
        const voices = speechSynthesis.getVoices();
        
        if (voices.length === 0) {
            console.log('❌ No voices available');
            return;
        }
        
        console.log('Available voices:', voices.length);
        
        // Test different voices to find the loudest one
        let voiceIndex = 0;
        const testText = "Testing voice volume level";
        
        function testNextVoice() {
            if (voiceIndex >= Math.min(voices.length, 10)) { // Test max 10 voices
                console.log('🎯 Voice test completed! Listen and compare volumes.');
                return;
            }
            
            const voice = voices[voiceIndex];
            console.log(`Testing voice ${voiceIndex + 1}: ${voice.name} (${voice.lang})`);
            
            speechSynthesis.cancel();
            const testUtterance = new SpeechSynthesisUtterance(`Voice number ${voiceIndex + 1}: ${voice.name}`);
            testUtterance.voice = voice;
            testUtterance.volume = 1.0;
            testUtterance.rate = 0.8;
            testUtterance.pitch = 1.0;
            
            testUtterance.onend = () => {
                voiceIndex++;
                setTimeout(testNextVoice, 1000); // 1 second pause between voices
            };
            
            testUtterance.onerror = () => {
                voiceIndex++;
                setTimeout(testNextVoice, 500);
            };
            
            speechSynthesis.speak(testUtterance);
        }
        
        testNextVoice();
    };

    // Speech Recognition Functions
    function initializeSpeechRecognition() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.lang = 'en-US';
            recognition.maxAlternatives = 3;
            
            // Add support for multiple languages
            const supportedLanguages = ['en-US', 'hi-IN', 'mr-IN'];
            recognition.lang = supportedLanguages[0]; // Default to English

            recognition.onstart = () => {
                isListening = true;
                voiceInputBtn.classList.add('listening');
                voiceInputBtn.title = 'Listening... Click to stop';
                voiceInputBtn.querySelector('i').className = 'fas fa-microphone-slash';
                
                // Stop any current speech output
                if (currentSpeech && speechSynthesis.speaking) {
                    stopCurrentSpeech();
                }
            };

            recognition.onresult = (event) => {
                let transcript = '';
                let isFinal = false;
                
                // Get the most confident result
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    if (event.results[i].isFinal) {
                        transcript += event.results[i][0].transcript;
                        isFinal = true;
                    } else {
                        // Show interim results
                        const interimTranscript = event.results[i][0].transcript;
                        chatInput.value = interimTranscript;
                        chatInput.style.fontStyle = 'italic';
                        chatInput.style.color = '#666';
                    }
                }
                
                if (isFinal && transcript.trim()) {
                    chatInput.value = transcript;
                    chatInput.style.fontStyle = 'normal';
                    chatInput.style.color = '#333';
                    chatInput.focus();
                    
                    // Visual feedback
                    voiceInputBtn.classList.remove('listening');
                    voiceInputBtn.classList.add('processing');
                    voiceInputBtn.title = 'Processing...';
                    voiceInputBtn.querySelector('i').className = 'fas fa-cog';
                    
                    setTimeout(() => {
                        voiceInputBtn.classList.remove('processing');
                        voiceInputBtn.title = 'Click to speak your question';
                        voiceInputBtn.querySelector('i').className = 'fas fa-microphone';
                        
                        // Auto-send the transcript
                        sendUserMessage(transcript);
                        hideQuickReplies();
                    }, 500);
                }
            };

            recognition.onerror = (event) => {
                console.log('Speech recognition error:', event.error);
                isListening = false;
                voiceInputBtn.classList.remove('listening', 'processing');
                voiceInputBtn.title = 'Click to speak your question';
                voiceInputBtn.querySelector('i').className = 'fas fa-microphone';
                
                let errorMessage = 'Voice recognition error';
                switch(event.error) {
                    case 'no-speech':
                        errorMessage = '🎤 No speech detected. Please try again.';
                        break;
                    case 'audio-capture':
                        errorMessage = '🎤 Microphone access denied. Please check permissions.';
                        break;
                    case 'not-allowed':
                        errorMessage = '🎤 Microphone permission required for voice input.';
                        break;
                    case 'network':
                        errorMessage = '🎤 Network error. Please check your connection.';
                        break;
                    default:
                        errorMessage = `🎤 Voice recognition error: ${event.error}`;
                }
                
                if (event.error !== 'aborted') {
                    addMessage(errorMessage, false, { error: true });
                }
            };

            recognition.onend = () => {
                isListening = false;
                voiceInputBtn.classList.remove('listening', 'processing');
                voiceInputBtn.title = 'Click to speak your question';
                voiceInputBtn.querySelector('i').className = 'fas fa-microphone';
            };

            // Show voice input button
            voiceInputBtn.style.display = 'flex';
        } else {
            // Hide voice input button if not supported
            voiceInputBtn.style.display = 'none';
            console.log('Speech Recognition not supported in this browser');
        }
    }

    function startVoiceInput() {
        if (!recognition) return;
        
        if (isListening) {
            // Stop listening
            recognition.stop();
        } else {
            try {
                // Try to detect preferred language from recent messages
                const recentMessages = document.querySelectorAll('.message.bot');
                if (recentMessages.length > 0) {
                    const lastBotMessage = recentMessages[recentMessages.length - 1].textContent;
                    const detectedLang = detectTextLanguage(lastBotMessage);
                    
                    // Set recognition language accordingly
                    if (detectedLang === 'hindi') {
                        recognition.lang = 'hi-IN';
                    } else if (detectedLang === 'marathi') {
                        recognition.lang = 'mr-IN';
                    } else {
                        recognition.lang = 'en-US';
                    }
                }
                
                recognition.start();
                
                // Provide user feedback about language
                const langFeedback = {
                    'hi-IN': 'हिंदी में बोलें',
                    'mr-IN': 'मराठीत बोला', 
                    'en-US': 'Speak now'
                };
                
                const currentLang = recognition.lang;
                voiceInputBtn.title = `${langFeedback[currentLang] || 'Speak now'} (${currentLang})`;
                
            } catch (error) {
                console.log('Failed to start speech recognition:', error);
                addMessage('🎤 Unable to start voice recognition. Please try again.', false, { error: true });
            }
        }
    }

    // Voice input button event
    voiceInputBtn.addEventListener('click', () => {
        startVoiceInput();
    });

    // Initialize speech recognition
    initializeSpeechRecognition();
    
    // Stop all speech activities when page is closed or refreshed
    window.addEventListener('beforeunload', () => {
        stopAllSpeechAndRecognition();
    });
    
    // Stop speech when page loses focus
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopAllSpeechAndRecognition();
        }
    });

    // Toggle chat window
    chatbotBtn.addEventListener("click", () => {
        isOpen = !isOpen;
        chatWindow.style.display = isOpen ? "flex" : "none";
        
        if (isOpen) {
            chatInput.focus();
            notificationBadge.style.display = "none";
            
            // Add welcome message if no messages exist
            if (chatMessages.children.length === 0) {
                addMessage("👋 Hello! I'm your PM Internship Assistant. How can I help you today?", false, { 
                    personalized: true, 
                    responseTime: '0.1' 
                });
                showQuickReplies();
            }
        } else {
            // When closing chat via toggle, stop all speech activities
            stopAllSpeechAndRecognition();
        }
    });

    // Close chat - Stop all speech activities
    closeChatBtn.addEventListener("click", () => {
        // Stop all speech and recognition activities
        stopAllSpeechAndRecognition();
        
        isOpen = false;
        chatWindow.style.display = "none";
    });

    // Escape key to close chat and stop speech
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && isOpen) {
            stopAllSpeechAndRecognition();
            isOpen = false;
            chatWindow.style.display = "none";
        }
    });

    // Stop all speech when page is about to unload
    window.addEventListener("beforeunload", () => {
        stopAllSpeechAndRecognition();
    });

    // Stop speech when page loses focus (user switches tabs)
    window.addEventListener("blur", () => {
        if (currentSpeech && speechSynthesis.speaking) {
            stopCurrentSpeech();
        }
    });

    // Quick reply buttons - use event delegation for both static and dynamic buttons
    const quickRepliesContainer = document.getElementById('quick-replies');
    if (quickRepliesContainer) {
        quickRepliesContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-reply-btn')) {
                const action = e.target.getAttribute('data-action');
                const message = e.target.getAttribute('data-message') || e.target.textContent;
                
                if (action === 'reload') {
                    location.reload();
                } else {
                    sendUserMessage(message);
                    hideQuickReplies();
                }
            }
        });
    }

    // Show notification badge for new messages
    function showNotificationBadge() {
        notificationBadge.style.display = "block";
        notificationBadge.textContent = "●";
        notificationBadge.style.animation = "bounce 0.6s ease-in-out";
    }

    // Enhanced add message function with metadata support
    function addMessage(content, isUser = false, metadata = {}) {
        const messageDiv = document.createElement("div");
        let messageClass = `message ${isUser ? 'user-message' : 'bot-message'}`;
        
        // Add special classes based on metadata
        if (metadata.error) messageClass += ' error-message';
        if (metadata.fallback) messageClass += ' fallback-message';
        if (metadata.personalized) messageClass += ' personalized-message';
        
        messageDiv.className = messageClass;
        
        const now = new Date();
        const time = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        // Enhanced message content with metadata
        let messageContent = `<div class="message-content">${content}</div>`;
        
        // Add metadata indicators
        let metaInfo = '';
        if (metadata.responseTime && parseFloat(metadata.responseTime) < 2) {
            metaInfo += '<span class="response-speed fast" title="Lightning fast response!">⚡</span>';
        }
        if (metadata.personalized) {
            metaInfo += '<span class="personalized-indicator" title="Personalized for you!">🎯</span>';
        }
        if (metadata.fallback) {
            metaInfo += '<span class="fallback-indicator" title="Smart fallback response">🧠</span>';
        }
        
        messageDiv.innerHTML = `
            ${messageContent}
            <div class="message-meta">
                <div class="message-time">${time}</div>
                <div class="message-indicators">${metaInfo}</div>
            </div>
        `;
        
        // Add smooth animation
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(20px)';
        
        chatMessages.appendChild(messageDiv);
        
        // Animate message appearance
        requestAnimationFrame(() => {
            messageDiv.style.transition = 'all 0.3s ease-out';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        });
        
        // Enhanced auto-scroll
        setTimeout(() => {
            chatMessages.scrollTo({
                top: chatMessages.scrollHeight,
                behavior: 'smooth'
            });
        }, 100);

        // Auto-speak bot messages if speech is enabled
        if (!isUser && speechEnabled && !metadata.error) {
            setTimeout(() => {
                speakText(content);
            }, 300);
        }
        
        // Show notification badge if chat is closed
        if (!isOpen && !isUser) {
            showNotificationBadge();
        }
    }

    // Show typing indicator
    function showTypingIndicator() {
        const typingDiv = document.createElement("div");
        typingDiv.className = "message bot-message";
        typingDiv.id = "typing-indicator";
        typingDiv.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Hide typing indicator
    function hideTypingIndicator() {
        const typingIndicator = document.getElementById("typing-indicator");
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    // Show/hide quick replies
    function showQuickReplies() {
        document.getElementById('quick-replies').style.display = 'flex';
    }

    function hideQuickReplies() {
        document.getElementById('quick-replies').style.display = 'none';
    }

    // Enhanced ultra-responsive send message function
    async function sendUserMessage(message) {
        if (!message.trim()) return;

        // Immediate UI feedback
        const trimmedMessage = message.trim();
        addMessage(trimmedMessage, true);
        chatInput.value = "";
        chatSend.disabled = true;
        
        // Enhanced visual feedback
        chatSend.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        chatInput.placeholder = "PRIA is thinking...";

        // Show enhanced typing indicator with personalization
        showTypingIndicator();
        
        // Performance tracking
        const startTime = performance.now();

        try {
            // Enhanced fetch with timeout and better error handling
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout
            
            const response = await fetch("/chat", {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({ 
                    message: trimmedMessage,
                    timestamp: new Date().toISOString()
                }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);
            hideTypingIndicator();

            if (response.ok) {
                const data = await response.json();
                const responseTime = performance.now() - startTime;
                
                // Add response with enhanced formatting
                addMessage(data.reply, false, {
                    personalized: data.personalized,
                    responseTime: data.response_time,
                    fallback: data.fallback
                });
                
                // Performance feedback (subtle)
                if (responseTime < 2000) {
                    console.log(`⚡ Fast response: ${responseTime.toFixed(0)}ms`);
                }
                
                // Smart quick replies based on response context
                setTimeout(() => {
                    showContextualQuickReplies(data.reply);
                }, 800);
                
                // Auto-scroll with smooth animation
                setTimeout(() => {
                    chatMessages.scrollTo({
                        top: chatMessages.scrollHeight,
                        behavior: 'smooth'
                    });
                }, 200);
                
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.reply || "⚠️ I'm having a small hiccup. Let me try a different approach!";
                addMessage(errorMessage, false, { error: true });
            }
        } catch (error) {
            hideTypingIndicator();
            
            let errorMessage;
            if (error.name === 'AbortError') {
                errorMessage = "⏱️ That's taking longer than usual. Let me give you a quick response instead!";
            } else if (error.message.includes('fetch')) {
                errorMessage = "🌐 Connection hiccup detected! I'm still here to help you though.";
            } else {
                errorMessage = "🤖 Oops! I encountered a small technical bump, but I'm resilient!";
            }
            
            addMessage(errorMessage, false, { error: true });
            console.error('Enhanced chat error handling:', error);
            
            // Show offline quick replies
            setTimeout(() => showOfflineQuickReplies(), 1000);
            
        } finally {
            // Reset UI elements
            chatSend.disabled = false;
            chatSend.innerHTML = '<i class="fas fa-paper-plane"></i>';
            chatInput.placeholder = "Type your message here...";
            
            // Re-focus input for better UX
            setTimeout(() => chatInput.focus(), 100);
        }
    }

    // Send button click
    chatSend.addEventListener("click", () => {
        sendUserMessage(chatInput.value);
        hideQuickReplies();
    });

    // Enter key press
    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            sendUserMessage(chatInput.value);
            hideQuickReplies();
        }
    });

    // Input validation with instant feedback
    chatInput.addEventListener("input", () => {
        const message = chatInput.value.trim();
        chatSend.disabled = !message;
        
        // Visual feedback for send button
        if (message) {
            chatSend.style.opacity = '1';
            chatSend.style.transform = 'scale(1)';
        } else {
            chatSend.style.opacity = '0.6';
            chatSend.style.transform = 'scale(0.95)';
        }
    });
    
    // Initialize send button state
    chatSend.style.opacity = '0.6';
    chatSend.style.transform = 'scale(0.95)';

    // Show notification after page load
    setTimeout(() => {
        if (!isOpen) {
            notificationBadge.style.display = "flex";
        }
    }, 3000);
});

// Replace or add this to your existing script section
document.addEventListener('DOMContentLoaded', function() {
    // Language Selector Functionality
    const languageBtn = document.getElementById('languageBtn');
    const languageOptions = document.getElementById('languageOptions');
    
    console.log('Language elements:', { languageBtn, languageOptions });
    
    if (languageBtn && languageOptions) {
        console.log('Language selector initialized');
        
        languageBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Language button clicked');
            
            const isVisible = languageOptions.classList.contains('show');
            console.log('Current visibility:', isVisible);
            
            languageOptions.classList.toggle('show');
            console.log('Toggled to:', languageOptions.classList.contains('show'));
        });

        document.addEventListener('click', function(e) {
            if (!languageBtn.contains(e.target) && !languageOptions.contains(e.target)) {
                languageOptions.classList.remove('show');
            }
        });

        // Close language options when clicking a language option
        languageOptions.querySelectorAll('.language-option').forEach(option => {
            option.addEventListener('click', function() {
                console.log('Language option clicked:', this.textContent);
                languageOptions.classList.remove('show');
            });
        });
    } else {
        console.error('Language selector elements not found:', { languageBtn, languageOptions });
    }
});

    // Enhanced contextual quick replies based on bot response
    function showContextualQuickReplies(botResponse) {
        const quickRepliesContainer = document.getElementById('quick-replies');
        if (!quickRepliesContainer) return;
        
        // Clear existing quick replies
        quickRepliesContainer.innerHTML = '';
        
        let contextualReplies = [];
        
        // Analyze response content for smart suggestions
        const responseLower = botResponse.toLowerCase();
        
        if (responseLower.includes('apply') || responseLower.includes('application')) {
            contextualReplies = [
                "How do I apply?",
                "What documents do I need?",
                "Check my eligibility",
                "Application deadline?"
            ];
        } else if (responseLower.includes('eligible') || responseLower.includes('criteria')) {
            contextualReplies = [
                "I meet all criteria - what's next?",
                "How to prove income limit?",
                "Documents needed for eligibility?",
                "Application process",
                "Check application deadlines"
            ];
        } else if (responseLower.includes('stipend') || responseLower.includes('benefit')) {
            contextualReplies = [
                "More about benefits",
                "When is payment?",
                "Additional allowances?",
                "How to apply?"
            ];
        } else if (responseLower.includes('document')) {
            contextualReplies = [
                "Document checklist",
                "Upload process",
                "Document verification",
                "What if I'm missing docs?"
            ];
        } else {
            // Default smart replies
            contextualReplies = [
                "Tell me more",
                "How do I start?",
                "What's next?",
                "Any tips?"
            ];
        }
        
        // Create quick reply buttons
        contextualReplies.forEach(reply => {
            const button = document.createElement('button');
            button.className = 'quick-reply-btn';
            button.textContent = reply;
            button.setAttribute('data-message', reply);
            // Event delegation handles the click, no need for onclick
            quickRepliesContainer.appendChild(button);
        });
        
        quickRepliesContainer.style.display = 'flex';
    }
    
    // Offline quick replies for when there's a connection issue
    function showOfflineQuickReplies() {
        const quickRepliesContainer = document.getElementById('quick-replies');
        if (!quickRepliesContainer) return;
        
        quickRepliesContainer.innerHTML = '';
        
        const offlineReplies = [
            "Try again",
            "Basic info",
            "Help",
            "Contact support"
        ];
        
        offlineReplies.forEach(reply => {
            const button = document.createElement('button');
            button.className = 'quick-reply-btn offline';
            button.textContent = reply;
            button.setAttribute('data-message', reply);
            if (reply === "Try again") {
                button.setAttribute('data-action', 'reload');
            }
            // Event delegation handles the click
            quickRepliesContainer.appendChild(button);
        });
        
        quickRepliesContainer.style.display = 'flex';
    }

// Simple Language Dropdown Function
function toggleLanguageDropdown() {
    console.log('Toggle function called');
    const dropdown = document.getElementById('languageDropdown');
    if (dropdown) {
        console.log('Dropdown found, current display:', window.getComputedStyle(dropdown).display);
        dropdown.classList.toggle('show');
        console.log('After toggle, has show class:', dropdown.classList.contains('show'));
    } else {
        console.error('Language dropdown not found');
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const dropdown = document.getElementById('languageDropdown');
    const button = document.querySelector('.language-btn');
    
    if (dropdown && button && !button.contains(event.target) && !dropdown.contains(event.target)) {
        dropdown.classList.remove('show');
    }
});

document.addEventListener('DOMContentLoaded', function() {
    // Profile Toggle Functionality
    const profileToggle = document.getElementById('profileToggle');
    const userProfile = document.querySelector('.user-profile');
    const mainContent = document.querySelector('.main-content');

    // Toggle profile sidebar
    profileToggle.addEventListener('click', function(e) {
        e.stopPropagation();
        userProfile.classList.toggle('active');
    });

    // Close sidebar when clicking outside
    document.addEventListener('click', function(e) {
        if (!userProfile.contains(e.target) && !profileToggle.contains(e.target)) {
            userProfile.classList.remove('active');
        }
    });

    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 992) {
            userProfile.classList.remove('active');
        }
    });

    // Prevent clicks inside sidebar from closing it
    userProfile.addEventListener('click', function(e) {
        e.stopPropagation();
    });
});
// Language Selector Functionality
document.addEventListener('DOMContentLoaded', function() {
    const languageBtn = document.getElementById('languageBtn');
    const languageOptions = document.getElementById('languageOptions');
    
    if (languageBtn && languageOptions) {
        languageBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            languageOptions.classList.toggle('show');
        });

        document.addEventListener('click', function(e) {
            if (!languageBtn.contains(e.target) && !languageOptions.contains(e.target)) {
                languageOptions.classList.remove('show');
            }
        });

        // Close language options when clicking a language option
        languageOptions.querySelectorAll('.language-option').forEach(option => {
            option.addEventListener('click', function() {
                languageOptions.classList.remove('show');
            });
        });
    }
});