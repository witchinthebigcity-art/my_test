(function () {
    const STYLE_CONFIGS = {
        neon: {skin: 0xf2b083, hair: 0x13bde1, hair2: 0x49f04d, top: 0xdfe7eb, accent: 0x39ed42, bottom: 0x151821, shoes: 0x35f04a, accessory: 'headphones', hairKind: 'spiky'},
        basket: {skin: 0xd99362, hair: 0x5a2e20, top: 0x16191b, accent: 0xff7425, bottom: 0x26282b, shoes: 0xf1f1ef, accessory: 'basketball', hairKind: 'spiky'},
        pixel: {skin: 0xf2af9b, hair: 0xff82c0, hair2: 0x35caef, top: 0xf7f8fa, accent: 0xff4aa6, bottom: 0x2c9ee8, shoes: 0xf7f8fa, accessory: 'controller', hairKind: 'long', cap: 0xf4f7fb},
        'pink-wave': {skin: 0xf2b69b, hair: 0xffd2ba, hair2: 0xff8fc1, top: 0xff86bb, accent: 0xffffff, bottom: 0x42a9db, shoes: 0xff8fbd, accessory: 'controller', hairKind: 'long'},
        'white-street': {skin: 0xdca078, hair: 0x33251f, top: 0xf0f1f1, accent: 0xe43b35, bottom: 0x151719, shoes: 0xf2f1ec, accessory: 'glasses', hairKind: 'short', hat: 0xf0f0ed},
        'aqua-pop': {skin: 0xf0aa83, hair: 0x202332, hair2: 0xff79aa, top: 0xff68a3, accent: 0x31d3da, bottom: 0x29cad2, shoes: 0x35d0d4, accessory: 'bracelets', hairKind: 'long', cap: 0xff6fa9},
        turbo: {skin: 0xd69b72, hair: 0x472b24, top: 0x159e9c, accent: 0xf24c9e, bottom: 0x202224, shoes: 0xf1f1ed, accessory: 'chain', hairKind: 'swept'},
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

    function buildHair(group, config) {
        const color = config.hair;
        if (config.hairKind === 'long') {
            sphere(group, .76, [0, 2.18, -.28], color, [1.08, 1.17, .8]);
            for (let index = 0; index < 7; index += 1) {
                const angle = (index / 6 - .5) * 2.15;
                const strandColor = index % 3 === 0 && config.hair2 ? config.hair2 : color;
                sphere(group, .32, [Math.sin(angle) * .88, 1.38 - Math.abs(angle) * .08, -.2 + Math.cos(angle) * .12], strandColor, [.75, 2.2, .62]);
            }
        } else if (config.hairKind === 'spiky') {
            for (let index = 0; index < 11; index += 1) {
                const angle = (index / 11) * Math.PI * 2;
                const strandColor = index % 3 === 0 && config.hair2 ? config.hair2 : color;
                const spike = addMesh(group, new THREE.ConeGeometry(.24, .9, 10), strandColor, [Math.cos(angle) * .58, 2.78 + Math.sin(angle * 2) * .08, Math.sin(angle) * .42], [Math.sin(angle) * .55, 0, -Math.cos(angle) * .55]);
                spike.rotation.y = -angle;
            }
            sphere(group, .69, [0, 2.3, -.05], color, [1, .72, .88]);
        } else {
            sphere(group, .74, [0, 2.3, -.1], color, [1.03, .72, .91]);
            if (config.hairKind === 'swept') {
                for (let index = 0; index < 5; index += 1) {
                    box(group, [.65, .25, .45], [-.38 + index * .17, 2.72 + index * .06, .05], color, [0, 0, -.35]);
                }
            }
        }
    }

    function buildFace(group, config) {
        box(group, [.15, .28, .05], [-.27, 2.15, .66], 0x17222a);
        box(group, [.15, .28, .05], [.27, 2.15, .66], 0x17222a);
        const smile = torus(group, .22, .035, [0, 1.9, .68], 0x552522, [0, 0, Math.PI]);
        smile.scale.y = .55;
        if (config.accessory === 'glasses') {
            box(group, [.57, .3, .08], [-.32, 2.18, .72], 0x111417);
            box(group, [.57, .3, .08], [.32, 2.18, .72], 0x111417);
            box(group, [.14, .07, .08], [0, 2.18, .73], 0x111417);
        }
    }

    function buildAccessories(group, config) {
        if (config.cap) {
            cylinder(group, .72, .76, .28, [0, 2.73, .04], config.cap);
            box(group, [.92, .11, .52], [0, 2.62, .52], config.cap, [-.08, 0, 0]);
        }
        if (config.hat) {
            cylinder(group, .78, .83, .36, [0, 2.78, 0], config.hat);
            cylinder(group, 1.05, 1.05, .1, [0, 2.58, .03], config.hat);
        }
        if (config.accessory === 'headphones') {
            torus(group, .78, .11, [0, 2.27, -.03], config.accent, [0, 0, 0]);
            box(group, [.2, .54, .33], [-.77, 2.22, 0], config.accent);
            box(group, [.2, .54, .33], [.77, 2.22, 0], config.accent);
        }
        if (config.accessory === 'basketball') {
            const ball = sphere(group, .45, [-1.55, .7, .52], 0xe96b25);
            torus(ball, .32, .018, [0, 0, 0], 0x291a15);
        }
        if (config.accessory === 'controller') {
            const controller = box(group, [.72, .32, .18], [1.45, .35, .65], 0x263244, [0, -.18, -.16]);
            sphere(controller, .055, [-.18, .04, .11], 0x24d7df);
            sphere(controller, .055, [.18, .04, .11], 0xff5a9e);
        }
        if (config.accessory === 'chain' || config.accessory === 'glasses') {
            torus(group, .45, .045, [0, .78, .67], 0xe2b34e, [Math.PI / 2, 0, 0]);
        }
        if (config.accessory === 'bracelets') {
            torus(group, .18, .045, [-1.2, .08, .03], 0xffd24a, [Math.PI / 2, 0, 0]);
            torus(group, .18, .045, [-1.2, -.02, .03], 0x29d4dc, [Math.PI / 2, 0, 0]);
        }
    }

    function buildCharacter(style) {
        const config = STYLE_CONFIGS[style] || STYLE_CONFIGS.neon;
        const root = new THREE.Group();
        const body = new THREE.Group();
        root.add(body);

        box(body, [1.42, 1.38, .86], [0, .63, 0], config.top);
        box(body, [1.44, .18, .9], [0, .02, 0], config.accent);
        box(body, [.56, 1.35, .62], [-.43, -1.03, 0], config.bottom);
        box(body, [.56, 1.35, .62], [.43, -1.03, 0], config.bottom);
        box(body, [.72, .36, 1.03], [-.43, -1.78, .16], config.shoes);
        box(body, [.72, .36, 1.03], [.43, -1.78, .16], config.shoes);

        box(body, [.42, 1.38, .48], [-1.0, .58, 0], config.skin, [0, 0, -.18]);
        box(body, [.42, 1.38, .48], [1.0, .58, 0], config.skin, [0, 0, .18]);
        box(body, [.52, .72, .62], [-1.0, .86, 0], config.top, [0, 0, -.18]);
        box(body, [.52, .72, .62], [1.0, .86, 0], config.top, [0, 0, .18]);
        sphere(body, .29, [-1.15, -.08, .02], config.skin, [.86, 1, .78]);
        sphere(body, .29, [1.15, -.08, .02], config.skin, [.86, 1, .78]);

        box(body, [1.43, 1.32, 1.3], [0, 2.12, 0], config.skin);
        buildHair(body, config);
        buildFace(body, config);
        buildAccessories(body, config);

        const chestStripe = box(body, [.85, .18, .06], [0, .75, .46], config.accent);
        chestStripe.material.roughness = .5;
        root.scale.set(.92, .92, .92);
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
        camera.position.set(0, .45, 8.3);
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
