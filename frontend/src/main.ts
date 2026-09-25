import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import '@fontsource-variable/public-sans/wght.css';
import './style.css';

const app = createApp(App).use(router);

// Resolve public routes before mounting components that fetch authenticated data.
router.isReady().then(() => app.mount('#app'));

