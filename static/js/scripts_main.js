document.addEventListener('DOMContentLoaded', () => {
    const navbarToggle = document.getElementById('navbar-toggle');
    const navbarMenu = document.getElementById('navbar-menu');
    const mainTab = document.getElementById('main-tab');
    const settingsTab = document.getElementById('settings-tab');
    const historyTab = document.getElementById('history-tab');
    const mainContent = document.getElementById('main-content');
    const settingsContent = document.getElementById('settings-content');
    const historyContent = document.getElementById('history-content');
    const voiceSelect = document.getElementById('voice-select');
    const testText = document.getElementById('test-text');
    const testVoiceButton = document.getElementById('test-voice-button');
    const video = document.getElementById('camera');
    const captureButton = document.getElementById('capture-button');
    const switchCameraButton = document.getElementById('switch-camera');
    const resultContainer = document.getElementById('result-container');
    const cameraContainer = document.getElementById('camera-container');
    const uploadContainer = document.getElementById('upload-container');
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const capturedImage = document.getElementById('captured-image');
    const caption = document.getElementById('caption');
    const replayCaptionButton = document.getElementById('replay-caption-button');
    const stopCaptionButton = document.getElementById('stop-caption-button');
    const closeButton = document.getElementById('close-button');
    const cameraTab = document.getElementById('camera-tab');
    const uploadTab = document.getElementById('upload-tab');
    const historyTableBody = document.getElementById('history-table-body');
    const historyModal = document.getElementById('history-modal');
    const modalImage = document.getElementById('modal-image');
    const modalCaption = document.getElementById('modal-caption');
    const modalReplayCaption = document.getElementById('modal-replay-caption');
    const modalStopCaption = document.getElementById('modal-stop-caption');
    const modalDelete = document.getElementById('modal-delete');
    const modalCloseButton = document.getElementById('modal-close-button');
    const closeModal = document.getElementById('close-modal');

    let currentStream;
    let useFrontCamera = true;
    let speechSynthesisUtterance;
    let recognition;
    let selectedVoice;
    let historyData = [];
    let currentModalIndex = null;

    function formatTanggalIndonesia(dateString) {
        const bulan = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ];
        
        const date = new Date(dateString);
        const day = date.getDate();
        const month = bulan[date.getMonth()];
        const year = date.getFullYear();
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        const seconds = date.getSeconds().toString().padStart(2, '0');
        
        return `${day} ${month} ${year} ${hours}:${minutes}:${seconds} WIB`;
    }

    navbarToggle.addEventListener('click', () => {
        navbarMenu.classList.toggle('hidden');
    });

    mainTab.addEventListener('click', () => {
        setActiveTab('main');
        mainContent.classList.remove('hidden');
        settingsContent.classList.add('hidden');
        historyContent.classList.add('hidden');
        stopCamera();
        initCamera();
    });

    settingsTab.addEventListener('click', () => {
        setActiveTab('settings');
        mainContent.classList.add('hidden');
        settingsContent.classList.remove('hidden');
        historyContent.classList.add('hidden');
        populateVoiceList();
        stopCamera();
    });

    historyTab.addEventListener('click', () => {
        setActiveTab('history');
        mainContent.classList.add('hidden');
        settingsContent.classList.add('hidden');
        historyContent.classList.remove('hidden');
        populateHistoryTable();
        stopCamera();
    });

    function setActiveTab(tab) {
        const tabs = ['main', 'settings', 'history'];
        tabs.forEach(t => {
            const element = document.getElementById(`${t}-tab`);
            if (t === tab) {
                element.classList.add('bg-blue-700');
            } else {
                element.classList.remove('bg-blue-700');
            }
        });
    }

    function populateVoiceList() {
        if (typeof speechSynthesis === 'undefined') {
            return;
        }

        const voices = speechSynthesis.getVoices().filter(voice => voice.lang.startsWith('id'));
        voiceSelect.innerHTML = '';

        voices.forEach(voice => {
            const option = document.createElement('option');
            option.textContent = `${voice.name} (${voice.lang})`;
            option.value = voice.name;
            voiceSelect.appendChild(option);
        });

        const savedVoiceName = localStorage.getItem('selectedVoice');
        if (savedVoiceName) {
            selectedVoice = voices.find(voice => voice.name === savedVoiceName);
            voiceSelect.value = savedVoiceName;
        } else if (voices.length > 0) {
            selectedVoice = voices[0];
        }

        voiceSelect.addEventListener('change', () => {
            selectedVoice = voices.find(voice => voice.name === voiceSelect.value);
            localStorage.setItem('selectedVoice', selectedVoice.name);
        });
    }

    // Populate voices when they change
    speechSynthesis.addEventListener('voiceschanged', populateVoiceList);

    testVoiceButton.addEventListener('click', () => {
        const text = testText.value;
        if (text && selectedVoice) {
            speakText(text, selectedVoice);
        }
    });

    function speakText(text, voice) {
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.voice = voice;
            utterance.lang = 'id-ID';
            window.speechSynthesis.speak(utterance);
        } else {
            showToastError('Sintesis suara tidak didukung di browser ini.');
        }
    }

    const isAndroid = /android/i.test(navigator.userAgent);
    const initialFacingMode = isAndroid ? 'environment' : 'user';

    const constraints = {
        video: {
            facingMode: initialFacingMode,
            width: { ideal: 1280 },
            height: { ideal: 720 }
        }
    };

    async function initCamera() {
        try {
            currentStream = await navigator.mediaDevices.getUserMedia(constraints);
            video.srcObject = currentStream;
        } catch (error) {
            console.error('Error accessing the camera: ', error);
            alert('Tidak dapat mengakses kamera. Silakan periksa pengaturan browser Anda.');
        }
    }

    function stopCamera() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
            currentStream = null;
        }
    }

    cameraTab.addEventListener('click', () => {
        cameraContainer.classList.remove('hidden');
        uploadContainer.classList.add('hidden');
        resultContainer.classList.add('hidden');
        cameraTab.classList.add('bg-blue-500', 'text-white');
        cameraTab.classList.remove('bg-gray-300');
        uploadTab.classList.add('bg-gray-300');
        uploadTab.classList.remove('bg-blue-500', 'text-white');
        stopSpeaking();
        initCamera();
        startSpeechRecognition();
    });

    uploadTab.addEventListener('click', () => {
        cameraContainer.classList.add('hidden');
        uploadContainer.classList.remove('hidden');
        resultContainer.classList.add('hidden');
        uploadTab.classList.add('bg-blue-500', 'text-white');
        uploadTab.classList.remove('bg-gray-300');
        cameraTab.classList.add('bg-gray-300');
        cameraTab.classList.remove('bg-blue-500', 'text-white');
        stopSpeaking();
        stopCamera();
        stopSpeechRecognition();
        fileInput.value = '';
    });

    captureButton.addEventListener('click', async () => {
        disableButtons(true);
        captureButton.textContent = 'Memproses...';

        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = canvas.toDataURL('image/png');
        capturedImage.src = imageData;

        stopCamera();
        video.srcObject = null;
        video.poster = imageData;

        await uploadImageAndGetCaption(imageData, 'camera');

        disableButtons(false);
        captureButton.textContent = 'Ambil Foto';
    });

    switchCameraButton.addEventListener('click', () => {
        useFrontCamera = !useFrontCamera;
        constraints.video.facingMode = useFrontCamera ? 'user' : 'environment';
        stopCamera();
        initCamera();
    });

    uploadButton.addEventListener('click', () => {
        const file = fileInput.files[0];
        if (!file) return;

        const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            alert('Format gambar tidak valid. Hanya menerima jpg, jpeg, png, dan webp.');
            return;
        }

        disableButtons(true);
        uploadButton.textContent = 'Memproses...';

        const reader = new FileReader();
        reader.onloadend = async () => {
            const imageData = reader.result;
            capturedImage.src = imageData;

            await uploadImageAndGetCaption(imageData, 'upload');
        };
        reader.readAsDataURL(file);
    });

    replayCaptionButton.addEventListener('click', () => {
        speakCaption(caption.textContent);
    });

    stopCaptionButton.addEventListener('click', () => {
        stopSpeaking();
    });

    closeButton.addEventListener('click', () => {
        resultContainer.classList.add('hidden');
        if (cameraTab.classList.contains('bg-blue-500')) {
            cameraContainer.classList.remove('hidden');
            initCamera();
            startSpeechRecognition();
        } else {
            uploadContainer.classList.remove('hidden');
        }
        stopSpeaking();
    });

    async function uploadImageAndGetCaption(imageData, source) {
        try {
            const formData = new FormData();
            formData.append('file', dataURItoBlob(imageData), 'image.jpg');

            const response = await fetch('/images', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Gagal mengunggah gambar: ${response.statusText}`);
            }

            const apiResponse = await response.json();
            const captionText = apiResponse.caption;
            caption.textContent = captionText;
            speakCaption(captionText);

            cameraContainer.classList.add('hidden');
            uploadContainer.classList.add('hidden');
            resultContainer.classList.remove('hidden');
        } catch (error) {
            console.error('Error:', error);
            showToastError(`Terjadi kesalahan saat mengunggah gambar: ${error.message}`);
        } finally {
            disableButtons(false);
            captureButton.textContent = 'Ambil Foto';
            uploadButton.textContent = 'Unggah';
        }
    }

    function dataURItoBlob(dataURI) {
        const byteString = atob(dataURI.split(',')[1]);
        const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0];
        const ab = new ArrayBuffer(byteString.length);
        const ia = new Uint8Array(ab);
        for (let i = 0; i < byteString.length; i++) {
            ia[i] = byteString.charCodeAt(i);
        }
        return new Blob([ab], { type: mimeString });
    }

    function speakCaption(text) {
        if ('speechSynthesis' in window) {
            speechSynthesisUtterance = new SpeechSynthesisUtterance(text);
            speechSynthesisUtterance.lang = 'id-ID';
            if (selectedVoice) {
                speechSynthesisUtterance.voice = selectedVoice;
            }
            window.speechSynthesis.speak(speechSynthesisUtterance);
        } else {
            showToastError('Sintesis suara tidak didukung di browser ini.');
        }
    }

    function stopSpeaking() {
        if (speechSynthesisUtterance) {
            window.speechSynthesis.cancel();
        }
    }

    function disableButtons(disable) {
        captureButton.disabled = disable;
        switchCameraButton.disabled = disable;
        uploadButton.disabled = disable;
        replayCaptionButton.disabled = disable;
        stopCaptionButton.disabled = disable;
        closeButton.disabled = disable;
    }

    function startSpeechRecognition() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
            recognition.lang = 'id-ID';
            recognition.continuous = true;
            recognition.interimResults = false;

            recognition.onresult = (event) => {
                const transcript = event.results[event.results.length - 1][0].transcript.trim().toLowerCase();
                if (['foto', 'potret', 'tangkap', 'capture'].includes(transcript)) {
                    captureButton.click();
                }
            };

            recognition.onerror = (event) => {
                console.error('Kesalahan pengenalan suara:', event.error);
            };

            recognition.start();
        } else {
            showToastError('Pengenalan suara tidak didukung di browser ini.');
        }
    }

    function stopSpeechRecognition() {
        if (recognition) {
            recognition.stop();
            recognition = null;
        }
    }

    async function populateHistoryTable() {
        historyTableBody.innerHTML = '';
        try {
            const response = await fetch('/images', {
                method: 'GET'
            });
            const images = await response.json();
            images.forEach((item, index) => {
                const row = document.createElement('tr');
                const formattedDate = formatTanggalIndonesia(item.upload_date);
                row.innerHTML = `
                    <td class="border px-4 py-2"><img src="${item.image_path}" class="w-16 h-16 object-cover cursor-pointer" onclick="showHistoryModal(${index})"></td>
                    <td class="border px-4 py-2">${item.predicted_caption}</td>
                    <td class="border px-4 py-2">${formattedDate}</td>
                `;
                historyTableBody.appendChild(row);
            });
            historyData = images;
        } catch (error) {
            console.error('Error fetching history:', error);
            showToastError('Terjadi kesalahan saat mengambil riwayat gambar.');
        }
    }

    window.showHistoryModal = function (index) {
        const item = historyData[index];
        modalImage.src = item.image_path;
        modalCaption.textContent = item.predicted_caption;
        currentModalIndex = index;
        historyModal.classList.remove('hidden');
    };

    modalReplayCaption.addEventListener('click', () => {
        const item = historyData[currentModalIndex];
        speakCaption(item.predicted_caption);
    });

    modalStopCaption.addEventListener('click', () => {
        stopSpeaking();
    });

    modalDelete.addEventListener('click', () => {
        const confirmDelete = confirm('Anda yakin ingin menghapus gambar ini?');
        if (confirmDelete) {
            deleteHistory(currentModalIndex);
            historyModal.classList.add('hidden');
        }
    });

    modalCloseButton.addEventListener('click', () => {
        historyModal.classList.add('hidden');
        stopSpeaking();
    });

    window.addEventListener('click', (event) => {
        if (event.target === historyModal) {
            historyModal.classList.add('hidden');
            stopSpeaking();
        }
    });

    async function deleteHistory(index) {
        const item = historyData[index];
        try {
            const response = await fetch(`/images/${item.id}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                historyData.splice(index, 1);
                populateHistoryTable();
            } else {
                console.error('Error deleting history:', response.statusText);
                showToastError('Terjadi kesalahan saat menghapus riwayat gambar.');
            }
        } catch (error) {
            console.error('Error deleting history:', error);
            showToastError('Terjadi kesalahan saat menghapus riwayat gambar.');
        }
    }

    mainTab.click();
});
