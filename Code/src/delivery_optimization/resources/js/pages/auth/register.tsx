import { Head } from '@inertiajs/react';
import TextLink from '@/components/text-link';
import { login } from '@/routes';

export default function Register() {
    return (
        <>
            <Head title="Inscription desactivee" />
            <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-5 text-center dark:border-slate-700 dark:bg-slate-800/60">
                <p className="text-sm text-slate-700 dark:text-slate-300">
                    La creation de compte est desactivee. Contactez un administrateur si vous avez besoin d'un acces.
                </p>
                <TextLink href={login()}>
                    Retour a la connexion
                </TextLink>
            </div>
        </>
    );
}

Register.layout = {
    title: 'Inscription indisponible',
    description: 'L acces est gere par un administrateur DRYV BOT',
};
