(function () {
    const STYLE_CONFIGS = {
        neon: {skin: 0xf2b083, hair: 0x13bde1, hair2: 0x49f04d, top: 0xdfe7eb, accent: 0x39ed42, bottom: 0x151821, shoes: 0x35f04a, accessory: 'headphones', hairKind: 'spiky', headShape: 'square'},
        basket: {skin: 0xd99362, hair: 0x5a2e20, top: 0x16191b, accent: 0xff7425, bottom: 0x26282b, shoes: 0xf1f1ef, accessory: 'basketball', hairKind: 'spiky', headShape: 'square'},
        pixel: {skin: 0xf2af9b, hair: 0xff82c0, hair2: 0x35caef, top: 0xf7f8fa, accent: 0xff4aa6, bottom: 0x2c9ee8, shoes: 0xf7f8fa, accessory: 'controller', hairKind: 'long', cap: 0xf4f7fb, headShape: 'round'},
        'pink-wave': {skin: 0xf2b69b, hair: 0xffd2ba, hair2: 0xff8fc1, top: 0xff86bb, accent: 0xffffff, bottom: 0x42a9db, shoes: 0xff8fbd, accessory: 'controller', hairKind: 'long', headShape: 'round'},
        'white-street': {skin: 0xdca078, hair: 0x33251f, top: 0xf0f1f1, accent: 0xe43b35, bottom: 0x151719, shoes: 0xf2f1ec, accessory: 'glasses', hairKind: 'short', hat: 0xf0f0ed, headShape: 'square'},
        'aqua-pop': {skin: 0xf0aa83, hair: 0x202332, hair2: 0xff79aa, top: 0xff68a3, accent: 0x31d3da, bottom: 0x29cad2, shoes: 0x35d0d4, accessory: 'bracelets', hairKind: 'long', cap: 0xff6fa9, headShape: 'square'},
        turbo: {skin: 0xd69b72, hair: 0x472b24, top: 0x159e9c, accent: 0xf24c9e, bottom: 0x202224, shoes: 0xf1f1ed, accessory: 'chain', hairKind: 'swept', headShape: 'square'},
    };

    let currentViewer = null;

    function material(color, roughness = 0.72, metalness = 0.04) {
        return new THREE.MeshStandardMaterial({color, roughness, metalness, flatShading: false});
    }

    function addMesh(group, geometry, color, position, rotation = null, scale = null, options = {}) {
        const mesh = new THREE.Mesh(geometry, material(color, options.roughness, options.metalness));
        mesh.position.set(...position);
        if (rotation) mesh.rotation.set(...rotation);
        if (scale) mesh.scale.set(...scale);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        group.add(mesh);
        return mesh;
    }

    function box(group, size, position, color, rotation = null) {
        return addMesh(group, new THREE.BoxGeometry(...size), color, position, rotation);
    }

    function sphere(group, radius, position, color, scale = null) {
        return addMesh(group, new THREE.SphereGeometry(radius, 28, 20), color, position, null, scale);
    }

    function cylinder(group, radiusTop, radiusBottom, height, position, color, rotation = null) {
        return addMesh(group, new THREE.CylinderGeometry(radiusTop, radiusBottom, height, 32), color, position, rotation);
    }

    function torus(group, radius, tube, position, color, rotation = null) {
        return addMesh(group, new THREE.TorusGeometry(radius, tube, 12, 36), color, position, rotation, null, {roughness: .4, metalness: .35});
    }

    function limbBetween(group, start, end, width, depth, color) {
        const dx = end[0] - start[0];
        const dy = end[1] - start[1];
        const length = Math.hypot(dx, dy) + .08;
        const center = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2, (start[2] + end[2]) / 2];
        return box(group, [width, length, depth], center, color, [0, 0, -Math.atan2(dx, dy)]);
    }

    function buildHair(group, config) {
        const color = config.hair;
        if (config.headShape === 'round') {
            sphere(group, .82, [0, 2.2, -.2], color, [1.06, 1.08, .92]);
            if (config.hairKind === 'long') {
                for (let index = 0; index < 6; index += 1) {
                    const side = index < 3 ? -1 : 1;
                    const row = index % 3;
                    const strandColor = row === 1 && config.hair2 ? config.hair2 : color;
                    sphere(group, .3, [side * (.72 + row * .1), 1.75 - row * .38, -.12], strandColor, [.72, 1.65, .64]);
                }
            }
            return;
        }

        box(group, [1.46, .3, 1.27], [0, 2.72, -.02], color);
        if (config.hairKind === 'spiky') {
            for (let index = 0; index < 7; index += 1) {
                const x = -.62 + index * .21;
                const strandColor = index % 3 === 0 && config.hair2 ? config.hair2 : color;
                addMesh(group, new THREE.ConeGeometry(.18, .62, 8), strandColor, [x, 3.0 + (index % 2) * .08, -.02], [0, 0, (index - 3) * -.08]);
            }
        } else if (config.hairKind === 'long') {
            box(group, [.25, 1.18, 1.08], [-.73, 1.92, -.08], color);
            box(group, [.25, 1.18, 1.08], [.73, 1.92, -.08], config.hair2 || color);
        } else if (config.hairKind === 'swept') {
            for (let index = 0; index < 5; index += 1) {
                box(group, [.5, .22, .48], [-.42 + index * .19, 2.78 + index * .06, .18], color, [0, 0, -.28]);
            }
        }
    }

    function buildFace(group, config) {
        const faceZ = config.headShape === 'round' ? .76 : .67;
        sphere(group, .095, [-.27, 2.18, faceZ], 0x17222a, [.82, 1.28, .46]);
        sphere(group, .095, [.27, 2.18, faceZ], 0x17222a, [.82, 1.28, .46]);
        sphere(group, .14, [0, 1.92, faceZ + .01], 0x7c3440, [1.28, .45, .32]);
        sphere(group, .06, [0, 1.95, faceZ + .045], 0xffffff, [1.25, .35, .22]);
        if (config.accessory === 'glasses') {
            box(group, [.55, .3, .07], [-.31, 2.2, faceZ + .05], 0x111417);
            box(group, [.55, .3, .07], [.31, 2.2, faceZ + .05], 0x111417);
            box(group, [.14, .07, .07], [0, 2.2, faceZ + .06], 0x111417);
        }
    }

    function buildArms(group, config) {
        const leftShoulder = [-.76, .98, 0];
        const rightShoulder = [.76, .98, 0];
        let leftElbow = [-1.04, .32, .06];
        let rightElbow = [1.04, .32, .06];
        let leftHand = [-1.04, -.3, .1];
        let rightHand = [1.04, -.3, .1];

        if (config.accessory === 'controller') {
            leftHand = [-.58, -.22, .55];
            rightHand = [.58, -.22, .55];
        } else if (config.accessory === 'basketball') {
            leftElbow = [-1.12, .82, .16];
            leftHand = [-1.24, 1.12, .42];
        }

        limbBetween(group, leftShoulder, leftElbow, .52, .6, config.top);
        limbBetween(group, rightShoulder, rightElbow, .52, .6, config.top);
        limbBetween(group, leftElbow, leftHand, .39, .46, config.skin);
        limbBetween(group, rightElbow, rightHand, .39, .46, config.skin);
        sphere(group, .27, leftHand, config.skin, [.9, 1, .82]);
        sphere(group, .27, rightHand, config.skin, [.9, 1, .82]);
        return {leftHand, rightHand};
    }

    function buildAccessories(group, config, pose) {
        if (config.cap) {
            cylinder(group, .72, .76, .26, [0, 2.86, .01], config.cap);
            box(group, [.92, .1, .5], [0, 2.75, .52], config.cap, [-.08, 0, 0]);
        }
        if (config.hat) {
            cylinder(group, .76, .8, .34, [0, 2.91, 0], config.hat);
            cylinder(group, 1.02, 1.02, .09, [0, 2.72, .03], config.hat);
        }
        if (config.accessory === 'headphones') {
            addMesh(group, new THREE.TorusGeometry(.79, .09, 12, 32, Math.PI), config.accent, [0, 2.28, -.02]);
            box(group, [.2, .54, .34], [-.78, 2.23, 0], config.accent);
            box(group, [.2, .54, .34], [.78, 2.23, 0], config.accent);
        }
        if (config.accessory === 'basketball') {
            const ballPosition = [pose.leftHand[0], pose.leftHand[1] + .43, pose.leftHand[2] + .03];
            sphere(group, .43, ballPosition, 0xe96b25);
            torus(group, .32, .018, ballPosition, 0x291a15);
            torus(group, .32, .018, ballPosition, 0x291a15, [0, Math.PI / 2, 0]);
        }
        if (config.accessory === 'controller') {
            const controller = box(group, [1.08, .34, .2], [0, -.22, .66], 0x263244, [0, 0, 0]);
            sphere(controller, .055, [-.19, .04, .12], 0x24d7df);
            sphere(controller, .055, [.19, .04, .12], 0xff5a9e);
        }
        if (config.accessory === 'chain' || config.accessory === 'glasses') {
            limbBetween(group, [-.38, .96, .49], [0, .7, .5], .065, .065, 0xe2b34e);
            limbBetween(group, [0, .7, .5], [.38, .96, .49], .065, .065, 0xe2b34e);
        }
        if (config.accessory === 'bracelets') {
            torus(group, .18, .045, [pose.leftHand[0], pose.leftHand[1] + .2, pose.leftHand[2]], 0xffd24a, [Math.PI / 2, 0, 0]);
        }
    }

    function buildCharacter(style) {
        const config = STYLE_CONFIGS[style] || STYLE_CONFIGS.neon;
        const root = new THREE.Group();
        const body = new THREE.Group();
        root.add(body);

        box(body, [1.42, 1.45, .86], [0, .55, 0], config.top);
        box(body, [1.46, .34, .92], [0, -.25, 0], config.accent);
        box(body, [.58, 1.55, .64], [-.42, -1.02, 0], config.bottom);
        box(body, [.58, 1.55, .64], [.42, -1.02, 0], config.bottom);
        box(body, [.74, .42, 1.04], [-.42, -1.82, .17], config.shoes);
        box(body, [.74, .42, 1.04], [.42, -1.82, .17], config.shoes);

        cylinder(body, .27, .3, .34, [0, 1.38, 0], config.skin);
        if (config.headShape === 'round') {
            sphere(body, .78, [0, 2.14, .03], config.skin, [1, 1.02, .94]);
        } else {
            box(body, [1.43, 1.38, 1.3], [0, 2.14, 0], config.skin);
        }
        buildHair(body, config);
        buildFace(body, config);
        const pose = buildArms(body, config);
        buildAccessories(body, config, pose);

        const chestStripe = box(body, [.85, .18, .06], [0, .7, .46], config.accent);
        chestStripe.material.roughness = .5;
        root.scale.set(.9, .9, .9);
        return root;
    }

    function disposeViewer() {
        if (!currentViewer) return;
        cancelAnimationFrame(currentViewer.frame);
        currentViewer.observer.disconnect();
        currentViewer.root.traverse((object) => {
            if (object.geometry) object.geometry.dispose();
            if (object.material) object.material.dispose();
        });
        currentViewer.renderer.dispose();
        currentViewer = null;
    }

    function mount(container, style) {
        disposeViewer();
        if (!window.THREE) {
            container.textContent = 'Не удалось загрузить модуль 3D. Откройте приложение заново.';
            return;
        }
        container.replaceChildren();
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(34, 1, .1, 100);
        camera.position.set(0, .45, 9.5);
        const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true, powerPreference: 'low-power'});
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);

        scene.add(new THREE.HemisphereLight(0xffffff, 0x273046, 2.25));
        const key = new THREE.DirectionalLight(0xffffff, 3.2);
        key.position.set(4, 6, 7);
        key.castShadow = true;
        scene.add(key);
        const rim = new THREE.DirectionalLight(0x69dff0, 2.1);
        rim.position.set(-5, 3, -3);
        scene.add(rim);

        const root = buildCharacter(style);
        root.position.y = -.15;
        scene.add(root);
        const base = cylinder(scene, 1.75, 2.05, .22, [0, -2.05, 0], 0x283245);
        base.material.metalness = .35;

        let targetRotation = -.18;
        let dragging = false;
        let lastX = 0;
        renderer.domElement.addEventListener('pointerdown', (event) => {
            dragging = true;
            lastX = event.clientX;
            renderer.domElement.setPointerCapture(event.pointerId);
        });
        renderer.domElement.addEventListener('pointermove', (event) => {
            if (!dragging) return;
            targetRotation += (event.clientX - lastX) * .012;
            lastX = event.clientX;
        });
        renderer.domElement.addEventListener('pointerup', () => { dragging = false; });
        renderer.domElement.addEventListener('pointercancel', () => { dragging = false; });

        const resize = () => {
            const width = Math.max(container.clientWidth, 280);
            const height = Math.max(container.clientHeight, 300);
            renderer.setSize(width, height, false);
            camera.aspect = width / height;
            camera.updateProjectionMatrix();
        };
        const observer = new ResizeObserver(resize);
        observer.observe(container);
        resize();

        const viewer = {renderer, root, observer, frame: 0};
        currentViewer = viewer;
        const animate = () => {
            if (currentViewer !== viewer) return;
            if (!dragging) targetRotation += .0022;
            root.rotation.y += (targetRotation - root.rotation.y) * .08;
            root.position.y = -.15 + Math.sin(performance.now() * .0015) * .025;
            renderer.render(scene, camera);
            viewer.frame = requestAnimationFrame(animate);
        };
        animate();
    }

    window.characterViewer = {mount, dispose: disposeViewer};
})();
