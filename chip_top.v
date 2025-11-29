
module chip_top(input clk, input rst_n, output [7:0] gpio_a, output [7:0] gpio_b);
  wire [7:0] A, B, Y_add, Y_xor;
  simple_rom u_rom (.addr(1'b0), .data(A));
  simple_rom u_rom2(.addr(1'b1), .data(B));
  simple_alu u_add (.a(A), .b(B), .op(2'b00), .y(Y_add));
  simple_alu u_xor (.a(A), .b(B), .op(2'b10), .y(Y_xor));
  assign gpio_a = Y_add;
  assign gpio_b = Y_xor;
endmodule
