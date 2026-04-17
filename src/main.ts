import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';
import * as THREE from 'three';

// ─── 1. INITIALIZE VIEWER ──────────────────────────────────────────────────
const viewer = new GaussianSplats3D.Viewer({
    rootElement: document.getElementById('app')!,
    sharedMemoryForWorkers: false,
    selfDrivenMode: true,
    useBuiltInControls: false,
    webXRMode: GaussianSplats3D.WebXRMode.VR,
    gpuAcceleratedSort: true,
    sphericalHarmonicsDegree: 2,
});

// PlayCanvas Colors
const renderer = (viewer as any).renderer || (viewer as any).webGLRenderer;
if (renderer) {
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
}

// ─── 2. SETUP CAMERA (NO RIG!) ─────────────────────────────────────────────
viewer.start();
const internalScene = viewer.scene || viewer.threeScene;

// Set the rotation order so mouse look doesn't flip upside down
viewer.camera.rotation.order = 'YXZ';

// ─── 3. WASD & MOUSE LOOK CONTROLS ─────────────────────────────────────────
const keys: Record<string, boolean> = {};
window.addEventListener('keydown', (e) => keys[e.code] = true);
window.addEventListener('keyup', (e) => keys[e.code] = false);

let isDragging = false;
let prevMouse = { x: 0, y: 0 };

document.getElementById('app')!.addEventListener('mousedown', (e) => {
    if (e.button === 0) { isDragging = true; prevMouse = { x: e.clientX, y: e.clientY }; }
});
window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const deltaX = e.clientX - prevMouse.x;
    const deltaY = e.clientY - prevMouse.y;
    prevMouse = { x: e.clientX, y: e.clientY };

    // Rotate the camera DIRECTLY
    viewer.camera.rotation.y -= deltaX * 0.002;
    viewer.camera.rotation.x -= deltaY * 0.002;
    viewer.camera.rotation.x = Math.max(-Math.PI/2, Math.min(Math.PI/2, viewer.camera.rotation.x));
});
window.addEventListener('mouseup', (e) => { if (e.button === 0) isDragging = false; });

function updateMovement() {
    const moveSpeed = 0.05;
    const direction = new THREE.Vector3();
    const cameraQuat = new THREE.Quaternion();

    viewer.camera.getWorldQuaternion(cameraQuat);
    const front = new THREE.Vector3(0, 0, -1).applyQuaternion(cameraQuat);
    const right = new THREE.Vector3(1, 0, 0).applyQuaternion(cameraQuat);

    if (keys['KeyW']) direction.add(front);
    if (keys['KeyS']) direction.sub(front);
    if (keys['KeyD']) direction.add(right);
    if (keys['KeyA']) direction.sub(right);

    if (direction.lengthSq() > 0) {
        direction.normalize().multiplyScalar(moveSpeed);
        // Move the camera DIRECTLY
        viewer.camera.position.add(direction);
    }
    requestAnimationFrame(updateMovement);
}
updateMovement();

// ─── 4. DYNAMIC MODEL LOADER ───────────────────────────────────────────────
const modelSelect = document.getElementById('model-select') as HTMLSelectElement;
const loadingText = document.getElementById('loading-text')!;

const plyFiles = import.meta.glob('/public/*.ply');
const availableModels = Object.keys(plyFiles).map(path => path.replace('/public', ''));

availableModels.forEach(modelPath => {
    const option = document.createElement('option');
    option.value = modelPath;
    option.innerText = modelPath.replace('/', '').replace('.ply', '').replace(/_/g, ' ');
    modelSelect.appendChild(option);
});

let currentSceneIndex = -1;
let isSwapping = false;

async function loadSplatModel(modelPath: string) {
    if (isSwapping) return;
    try {
        isSwapping = true;
        modelSelect.disabled = true;
        loadingText.innerText = "Loading Model...";

        if (currentSceneIndex !== -1) {
            await (viewer as any).removeSplatScene(currentSceneIndex);
        }

        await viewer.addSplatScene(modelPath, {
            splatAlphaRemovalThreshold: 5,
            showLoadingUI: false,
            rotation: [1, 0, 0, 0],
        });

        currentSceneIndex = 0;

        // Auto-Center math applied directly to the camera!
        const boundingBox = new THREE.Box3().setFromObject(internalScene);
        const center = new THREE.Vector3();
        boundingBox.getCenter(center);

        // Place the user in the middle of the room, standing 1.6m high
        viewer.camera.position.set(center.x, center.y + 1.6, center.z);

        // Look straight ahead
        viewer.camera.rotation.set(0, 0, 0);

        loadingText.innerText = "";

    } catch (e) {
        console.error(e);
        loadingText.innerText = "Error loading model!";
    } finally {
        isSwapping = false;
        modelSelect.disabled = false;
    }
}

modelSelect.addEventListener('change', (e) => {
    loadSplatModel((e.target as HTMLSelectElement).value);
});

if (availableModels.length > 0) {
    loadSplatModel(availableModels[0]);
} else {
    loadingText.innerText = "No .ply files found in /public";
}