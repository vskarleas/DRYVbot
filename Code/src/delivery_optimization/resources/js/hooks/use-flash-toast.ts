import { router } from '@inertiajs/react';
import { useEffect } from 'react';
import { toast } from 'sonner';

export function useFlashToast(): void {
    useEffect(() => {
        return router.on('navigate', (event) => {
            const flash = event.detail.page.props.flash as {
                success?: string;
                error?: string;
            };

            if (flash?.success) toast.success(flash.success);
            if (flash?.error) toast.error(flash.error);
        });
    }, []);
}
