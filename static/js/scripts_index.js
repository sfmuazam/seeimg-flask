document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('camera');
    const captureButton = document.getElementById('capture-button');
    const switchCameraButton = document.getElementById('switch-camera');
    const resultContainer = document.getElementById('result-container');
    const cameraContainer = document.getElementById('camera-container');
    const uploadContainer = document.getElementById('upload-container');
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const filePreview = document.getElementById('file-preview');
    const capturedImage = document.getElementById('captured-image');
    const caption = document.getElementById('caption');
    const replayCaptionButton = document.getElementById('replay-caption-button');
    const stopCaptionButton = document.getElementById('stop-caption-button');
    const closeButton = document.getElementById('close-button');
    const cameraTab = document.getElementById('camera-tab');
    const uploadTab = document.getElementById('upload-tab');
    const sampleImages = document.getElementById('sample-images');

    let currentStream;
    let useFrontCamera = true;
    let speechSynthesisUtterance;
    let recognition;
    let selectedVoice;
    let currentMode = 'camera';  
    const isAndroid = /android/i.test(navigator.userAgent);
    const initialFacingMode = isAndroid ? 'environment' : 'user';

    // Determine constraints based on device type
    const constraints = {
        video: {
            facingMode: initialFacingMode,
            width: isMobileDevice() ? { ideal: 1280 } : { ideal: 1280 },
            height: isMobileDevice() ? { ideal: 960 } : { ideal: 720 }
        }
    };

    function isMobileDevice() {
        return /Mobi|Android/i.test(navigator.userAgent);
    }

    cameraTab.addEventListener('click', () => {
        switchMode('camera');
    });

    uploadTab.addEventListener('click', () => {
        switchMode('upload');
    });

    fileInput.addEventListener('change', () => {
        handleFileInput();
    });

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

    captureButton.addEventListener('click', async () => {
        await captureImage();
    });

    switchCameraButton.addEventListener('click', () => {
        toggleCamera();
    });

    uploadButton.addEventListener('click', () => {
        handleUpload();
    });

    replayCaptionButton.addEventListener('click', () => {
        speakCaption(caption.textContent);
    });

    stopCaptionButton.addEventListener('click', () => {
        stopSpeaking();
    });

    closeButton.addEventListener('click', () => {
        closeResultContainer();
    });

    async function captureImage() {
        disableButtons(true);
        captureButton.innerHTML = 'Memproses... <svg class="animate-spin h-5 w-5 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zM2 12a10 10 0 0110-10v2A8 8 0 004 12H2zm20 0a8 8 0 01-8 8v2c6.627 0 12-5.373 12-12h-4zm-2 0a10 10 0 01-10 10v-2a8 8 0 008-8h2z"></path></svg>';

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

        try {
            await getCaption(imageData, 'camera');
        } catch (error) {
            showToastError('Terjadi kesalahan saat mengunggah gambar.');
        }

        disableButtons(false);
        captureButton.innerHTML = 'Ambil Foto';
    }

    function toggleCamera() {
        useFrontCamera = !useFrontCamera;
        constraints.video.facingMode = useFrontCamera ? 'user' : 'environment';
        stopCamera();
        initCamera();
    }

    function handleFileInput() {
        const file = fileInput.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = () => {
                filePreview.src = reader.result;
                filePreview.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        } else {
            filePreview.classList.add('hidden');
        }
    }

    async function handleUpload() {
        const file = fileInput.files[0];
        if (!file) return;

        const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            alert('Format gambar tidak valid. Hanya menerima jpg, jpeg, png, dan webp.');
            return;
        }

        disableButtons(true);
        uploadButton.innerHTML = 'Memproses... <svg class="animate-spin h-5 w-5 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zM2 12a10 10 0 0110-10v2A8 8 0 004 12H2zm20 0a8 8 0 01-8 8v2c6.627 0 12-5.373 12-12h-4zm-2 0a10 10 0 01-10 10v-2a8 8 0 008-8h2z"></path></svg>';

        const reader = new FileReader();
        reader.onloadend = async () => {
            const imageData = reader.result;
            capturedImage.src = imageData;

            try {
                await getCaption(imageData, 'upload');
            } catch (error) {
                showToastError('Terjadi kesalahan saat mengunggah gambar.');
            }

            disableButtons(false);
            uploadButton.innerHTML = 'Unggah';
        };
        reader.readAsDataURL(file);
    }

    async function getCaption(imageData, source) {
        const formData = new FormData();
        formData.append('file', dataURItoBlob(imageData), 'image.jpg');

        const response = await fetch('/captioning', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to get caption');
        }

        const data = await response.json();
        const captionText = data.caption;
        caption.textContent = captionText;
        speakCaption(captionText);

        cameraContainer.classList.add('hidden');
        uploadContainer.classList.add('hidden');
        resultContainer.classList.remove('hidden');
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

    function closeResultContainer() {
        resultContainer.classList.add('hidden');
        if (currentMode === 'camera') {
            cameraContainer.classList.remove('hidden');
            initCamera();
            startSpeechRecognition();
        } else if (currentMode === 'upload') {
            uploadContainer.classList.remove('hidden');
        }
        stopSpeaking();
    }

    function switchMode(mode) {
        currentMode = mode;
        if (mode === 'camera') {
            cameraContainer.classList.remove('hidden');
            uploadContainer.classList.add('hidden');
            resultContainer.classList.add('hidden');
            cameraTab.classList.add('bg-blue-500', 'text-white');
            cameraTab.classList.remove('bg-gray-300');
            uploadTab.classList.add('bg-gray-300');
            uploadTab.classList.remove('bg-blue-500', 'text-white');
            sampleImages.classList.add('hidden');
            stopSpeaking();
            initCamera();
            startSpeechRecognition();
        } else if (mode === 'upload') {
            cameraContainer.classList.add('hidden');
            uploadContainer.classList.remove('hidden');
            resultContainer.classList.add('hidden');
            uploadTab.classList.add('bg-blue-500', 'text-white');
            uploadTab.classList.remove('bg-gray-300');
            cameraTab.classList.add('bg-gray-300');
            cameraTab.classList.remove('bg-blue-500', 'text-white');
            sampleImages.classList.remove('hidden');
            stopSpeaking();
            stopCamera();
            stopSpeechRecognition();
            fileInput.value = '';
            filePreview.classList.add('hidden');
        }
    }

    cameraTab.click();
});
