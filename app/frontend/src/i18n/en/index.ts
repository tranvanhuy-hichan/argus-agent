import admin from './admin.ts'
import catalog from './catalog.ts'
import chat from './chat.ts'
import composer from './composer.ts'
import core from './core.ts'
import features from './features.ts'
import home from './home.ts'
import security from './security.ts'

/** Ban dich tieng Anh, khoa la cau tieng Viet goc. Moi nhom file nam rieng de de bao tri. */
export const EN: Record<string, string> = { ...core, ...chat, ...catalog, ...admin, ...home, ...composer, ...security, ...features }
