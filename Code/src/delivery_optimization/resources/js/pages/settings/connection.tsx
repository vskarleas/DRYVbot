import { Form, Head } from '@inertiajs/react';
import ConnectionController from '@/actions/App/Http/Controllers/Settings/ConnectionController';
import Heading from '@/components/heading';
import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { edit } from '@/routes/connection';

type Connection = {
    scheme: string;
    host: string;
    port: number | null;
};

export default function Connection({
    connection,
}: {
    connection: Connection;
}) {
    return (
        <>
            <Head title="Connection settings" />

            <h1 className="sr-only">Connection settings</h1>

            <div className="space-y-6">
                <Heading
                    variant="small"
                    title="Connection"
                    description="Configure how the dashboard reaches the digital twin (ROS 2) socket"
                />

                <Form
                    {...ConnectionController.update.form()}
                    options={{ preserveScroll: true }}
                    className="space-y-6"
                >
                    {({ processing, errors }) => (
                        <>
                            <div className="grid gap-2">
                                <Label htmlFor="scheme">Protocol</Label>

                                <Select
                                    name="scheme"
                                    defaultValue={connection.scheme || 'ws'}
                                >
                                    <SelectTrigger id="scheme" className="w-full">
                                        <SelectValue placeholder="Select protocol" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="ws">
                                            ws — WebSocket
                                        </SelectItem>
                                        <SelectItem value="wss">
                                            wss — WebSocket (TLS)
                                        </SelectItem>
                                        <SelectItem value="tcp">
                                            tcp — raw TCP socket
                                        </SelectItem>
                                    </SelectContent>
                                </Select>

                                <InputError
                                    className="mt-2"
                                    message={errors.scheme}
                                />
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="host">IP address or host</Label>

                                <Input
                                    id="host"
                                    className="mt-1 block w-full"
                                    defaultValue={connection.host}
                                    name="host"
                                    required
                                    autoComplete="off"
                                    placeholder="192.168.1.42"
                                />

                                <InputError
                                    className="mt-2"
                                    message={errors.host}
                                />
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="port">Port</Label>

                                <Input
                                    id="port"
                                    type="number"
                                    min={1}
                                    max={65535}
                                    className="mt-1 block w-full"
                                    defaultValue={connection.port ?? ''}
                                    name="port"
                                    required
                                    placeholder="9090"
                                />

                                <InputError
                                    className="mt-2"
                                    message={errors.port}
                                />
                            </div>

                            <p className="text-sm text-muted-foreground">
                                The ROS 2 machine exposes the WebSocket bridge on
                                port 9090 by default. Changes apply to newly
                                started digital-twin socket workers.
                            </p>

                            <div className="flex items-center gap-4">
                                <Button
                                    disabled={processing}
                                    data-test="update-connection-button"
                                >
                                    Save
                                </Button>
                            </div>
                        </>
                    )}
                </Form>
            </div>
        </>
    );
}

Connection.layout = {
    breadcrumbs: [
        {
            title: 'Connection settings',
            href: edit(),
        },
    ],
};
