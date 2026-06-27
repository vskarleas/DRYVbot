<?php

namespace Database\Factories;

use App\Enums\OrderStatus;
use App\Models\Order;
use App\Models\Room;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

/**
 * @extends Factory<Order>
 */
class OrderFactory extends Factory
{
    public function definition(): array
    {
        return [
            'reference' => 'ORD-' . strtoupper(Str::random(8)),
            'created_by' => User::factory(),
            'departure_room_id' => Room::factory(),
            'arrival_room_id' => Room::factory(),
            'expected_delivery_at' => fake()->dateTimeBetween('now', '+7 days'),
            'status' => OrderStatus::Pending,
            'content' => fake()->optional()->paragraph(),
            'notes' => fake()->optional()->sentence(),
        ];
    }

    public function delivered(): static
    {
        return $this->state(fn () => [
            'status' => OrderStatus::Delivered,
            'delivered_at' => now(),
        ]);
    }

    public function inTransit(): static
    {
        return $this->state(fn () => ['status' => OrderStatus::InTransit]);
    }

    public function cancelled(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => OrderStatus::Cancelled,
            'cancelled_at' => now(),
            'cancellation_reason' => fake()->sentence(),
        ]);
    }
}
