import { Form, Head } from '@inertiajs/react';
import DtConnectionController from '@/actions/App/Http/Controllers/Settings/DtConnectionController';
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

type LastStatus = {
    state?: string;
    target?: string | null;
} | null;

export default function Connection({
    connection,
    lastStatus,
}: {
    connection: Connection;
    lastStatus: LastStatus;
}) {
    return (
        <>
            <Head title="Connection settings" />

            <h1 className="sr-only">Digital twin connection settings</h1>

            <div className="space-y-6">
                <Heading
                    variant="small"
                    title="Digital twin connection"
                    description="Set the address of the ROS machine on the network the app sends room commands to and receives navigation states from."
                />

                <div className="rounded-md border p-4 text-sm">
                    <div className="font-medium">Last received state</div>
                    {lastStatus?.state ? (
                        <p className="mt-1 text-muted-foreground">
                            {lastStatus.state}
                            {lastStatus.target
                                ? ` → ${lastStatus.target}`
                                : ''}
                        </p>
                    ) : (
                        <p className="mt-1 text-muted-foreground">
                            No state received from the digital twin yet.
                        </p>
                    )}
                </div>

                <Form
                    {...DtConnectionController.update.form()}
                    options={{ preserveScroll: true }}
                    className="space-y-6"
                >
                    {({ processing, errors }) => (
                        <>
                            <div className="grid gap-2">
                                <Label htmlFor="scheme">Protocol</Label>

                                <Select
                                    name="scheme"
                                    defaultValue={connection.scheme}
                                >
                                    <SelectTrigger id="scheme" className="w-full">
                                        <SelectValue placeholder="Select protocol" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="ws">
                                            ws (WebSocket — ROS ws_command_bridge)
                                        </SelectItem>
                                        <SelectItem value="wss">
                                            wss (WebSocket over TLS)
                                        </SelectItem>
                                        <SelectItem value="tcp">
                                            tcp (raw TCP socket)
                                        </SelectItem>
                                    </SelectContent>
                                </Select>

                                <InputError
                                    className="mt-2"
                                    message={errors.scheme}
                                />
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="host">
                                    ROS machine IP / hostname
                                </Label>

                                <Input
                                    id="host"
                                    className="mt-1 block w-full"
                                    defaultValue={connection.host}
                                    name="host"
                                    required
                                    placeholder="e.g. 192.168.1.42 or localhost"
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
                                    placeholder="e.g. 9090"
                                />

                                <InputError
                                    className="mt-2"
                                    message={errors.port}
                                />
                            </div>

                            <p className="text-sm text-muted-foreground">
                                The change is applied automatically: the running
                                socket workers reconnect to the new address within
                                a few seconds — no restart required.
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
